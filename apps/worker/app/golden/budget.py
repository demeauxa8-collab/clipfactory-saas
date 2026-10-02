"""Benchmark-only accounting at the HTTP boundary, including SDK retries.

Reserve conservative input/output ceilings *before* sending. Missing usage or
ambiguous transport errors retain the reservation; they are never assumed free.
No provider key settings or production provider code are changed.
"""

from __future__ import annotations

import contextvars
import importlib
import json
import math
import time
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

import httpx

source_context = contextvars.ContextVar("golden_source", default="")
duration_context = contextvars.ContextVar("golden_duration", default=0.0)


class BudgetExceeded(RuntimeError):
    pass


class Budget:
    def __init__(self, cap: str, path: Path, prices: dict, prior_entries=None):
        self.cap = Decimal(cap)
        if not Decimal("0") < self.cap <= Decimal("3"):
            raise ValueError("golden cap must be positive and at most $3")
        self.path, self.prices, self.entries = path, prices, list(prior_entries or [])
        if self.committed > self.cap:
            raise BudgetExceeded("prior attempts already exhaust this mission budget")
        if path.exists():
            raise ValueError("refusing to overwrite an existing budget ledger")
        self.save()

    @property
    def committed(self):
        return sum((Decimal(e["charged_or_reserved_usd"]) for e in self.entries), Decimal(0))

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "cap_usd": str(self.cap),
                    "charged_or_reserved_usd": str(self.committed),
                    "requests": self.entries,
                },
                indent=2,
            )
        )
        temporary.chmod(0o600)
        temporary.replace(self.path)

    def reserve(self, model: str, stage: str, amount: Decimal):
        if amount <= 0 or not amount.is_finite():
            raise ValueError("invalid cost bound")
        if self.committed + amount > self.cap:
            self.entries.append(
                {
                    "source": source_context.get(),
                    "stage": stage,
                    "model": model,
                    "charged_or_reserved_usd": "0",
                    "accounting": "blocked_before_send",
                    "required_reservation_usd": str(amount),
                }
            )
            self.save()
            raise BudgetExceeded("request blocked before sending: golden budget exhausted")
        entry = {
            "source": source_context.get(),
            "stage": stage,
            "model": model,
            "reserved_usd": str(amount),
            "charged_or_reserved_usd": str(amount),
            "accounting": "reserved",
            "started_monotonic": time.monotonic(),
        }
        self.entries.append(entry)
        self.save()
        return entry

    def settle(self, entry, amount, accounting, **usage):
        if amount is not None:
            amount = Decimal(str(amount))
            if not amount.is_finite() or amount < 0:
                raise ValueError("invalid provider cost")
            if amount > Decimal(entry["reserved_usd"]):
                # Halt immediately; never silently claim a violated ceiling held.
                entry["bound_violation"] = True
                entry["charged_or_reserved_usd"] = str(amount)
                self.save()
                raise BudgetExceeded("provider usage exceeded conservative request bound")
            entry["charged_or_reserved_usd"] = str(amount)
        entry.update(
            accounting=accounting,
            elapsed_seconds=time.monotonic() - entry["started_monotonic"],
            **usage,
        )
        self.save()

    def quote(self, body):
        model = body["model"]
        rates = self.prices[model]  # Unknown models fail closed.

        def tokens(value):
            if isinstance(value, str):
                return len(value.encode("utf-8")) + 8
            if isinstance(value, list):
                return sum(tokens(v) for v in value)
            if isinstance(value, dict):
                if value.get("type") in {"image_url", "image"}:
                    return 4096
                if value.get("type") == "video_url":
                    if duration_context.get() <= 0:
                        raise ValueError("video cost requires known duration")
                    # >10x documented default 1 fps video+audio tokenization.
                    return math.ceil(duration_context.get() + 1) * 4096
                return sum(tokens(v) for v in value.values())
            return 0

        input_bound = tokens(body.get("messages", [])) + tokens(body.get("system", "")) + 1024
        output_bound = int(body["max_tokens"])
        amount = (
            Decimal(input_bound) * Decimal(str(rates["input"]))
            + Decimal(output_bound) * Decimal(str(rates["output"]))
        ) * Decimal("1.1")
        if any(
            v.get("type") == "video_url"
            for m in body.get("messages", [])
            for v in (m.get("content") if isinstance(m.get("content"), list) else [])
        ):
            stage = "judge"
        elif model.startswith("qwen/"):
            stage = "vision_cheap"
        elif "image_url" in json.dumps(body.get("messages", [])):
            stage = "vision_deep"
        else:
            stage = "text"
        return model, stage, amount

    @contextmanager
    def intercept(self):
        budget = self
        clients = [httpx.AsyncClient]
        try:
            clients.append(importlib.import_module("httpx2").AsyncClient)
        except ImportError:
            pass
        originals = [(client, client.send) for client in clients]

        async def send(original, client, request, *args, **kwargs):
            host = request.url.host
            if request.method != "POST" or host not in {
                "api.openai.com",
                "openrouter.ai",
                "api.anthropic.com",
            }:
                return await original(client, request, *args, **kwargs)
            if host == "api.openai.com" and request.url.path == "/v1/audio/transcriptions":
                if duration_context.get() <= 0:
                    raise ValueError("ASR requires known source duration")
                model, stage = "whisper-1", "transcription"
                bound = Decimal(math.ceil(duration_context.get() + 1)) * Decimal("0.0001")
            elif request.url.path.endswith(("/chat/completions", "/messages")):
                body = json.loads(await request.aread())
                model, stage, bound = budget.quote(body)
            else:
                raise BudgetExceeded("unaccounted paid endpoint blocked")
            entry = budget.reserve(model, stage, bound)
            try:
                response = await original(client, request, *args, **kwargs)
                await response.aread()
            except BaseException:
                budget.settle(entry, None, "uncertain_transport_upper_bound")
                raise
            if response.status_code in {400, 401, 403, 404, 413, 422, 429}:
                budget.settle(entry, 0, "rejected_http", status=response.status_code)
                return response
            try:
                data = response.json()
                usage = data.get("usage", {})
                if stage == "transcription" and response.is_success and "duration" in data:
                    amount = Decimal(math.ceil(float(data["duration"]))) * Decimal("0.0001")
                    budget.settle(
                        entry, amount, "asr_duration_tariff", duration_seconds=data["duration"]
                    )
                elif host == "openrouter.ai" and usage.get("cost") is not None:
                    budget.settle(
                        entry,
                        usage["cost"],
                        "provider_reported",
                        generation_id=data.get("id"),
                        resolved_model=data.get("model"),
                        usage=usage,
                    )
                elif host == "api.anthropic.com" and response.is_success and usage:
                    rates = budget.prices[model]
                    amount = Decimal(usage.get("input_tokens", 0)) * Decimal(
                        str(rates["input"])
                    ) + Decimal(usage.get("output_tokens", 0)) * Decimal(str(rates["output"]))
                    # No prompt caching is requested by the production adapter.
                    if usage.get("cache_creation_input_tokens") or usage.get(
                        "cache_read_input_tokens"
                    ):
                        budget.settle(entry, None, "cached_usage_upper_bound", usage=usage)
                    else:
                        budget.settle(
                            entry,
                            amount,
                            "usage_tariff",
                            usage=usage,
                            resolved_model=data.get("model"),
                        )
                else:
                    budget.settle(
                        entry, None, "missing_usage_upper_bound", status=response.status_code
                    )
            except (ValueError, KeyError, TypeError):
                budget.settle(entry, None, "invalid_usage_upper_bound")
            return response

        def wrap(original):
            async def guarded(client, request, *args, **kwargs):
                return await send(original, client, request, *args, **kwargs)

            return guarded

        for client, original in originals:
            client.send = wrap(original)
        try:
            yield
        finally:
            for client, original in originals:
                client.send = original
