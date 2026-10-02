import json
from decimal import Decimal

import httpx
import pytest

from app.golden.budget import Budget, BudgetExceeded, duration_context
from app.golden.harness import PreloadJournal
from app.golden.judge import parse_verdict
from app.golden.metrics import audience_overlap, clip_metrics, normalize, union
from app.golden.review import generate_review
from app.golden.sources import sha256, verify_source
from app.pipeline.ffmpeg import _read_cached_heatmap


def test_preload_verifies_immutable_media_and_caches_absent_curve(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    media = source / "source.mp4"
    media.write_bytes(b"frozen source")
    (source / "meta.json").write_text(json.dumps({"sha256": sha256(media)}))
    (source / "heatmap.json").write_text("null")
    work = tmp_path / "work"
    PreloadJournal(source, work).start("job", "token")
    assert (work / "job/token/source.mp4").read_bytes() == b"frozen source"
    assert _read_cached_heatmap(work / "job/token/heatmap.json") == (True, None)
    media.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_source(source)


def test_metrics_detect_inner_word_cut_and_suspended_segment():
    words = [
        {"word": w, "start": i, "end": i + 0.8}
        for i, w in enumerate(["Ça", "marche", "mais", "fin"])
    ]
    transcript = {"words": words, "sentences": [{"end": 3.8}]}
    render = {
        "edl": {
            "shots": [
                {"from_word_id": 0, "to_word_id": 2, "source_in_ms": 200, "source_out_ms": 2800}
            ]
        },
        "technical_qc": {
            "duration_seconds": 20,
            "black_intervals": [[1, 2], [1.5, 3]],
            "silence_intervals": [],
        },
    }
    result = clip_metrics(render, transcript)
    assert result["suspended_ending"] and result["dependent_opening"]
    assert result["cut_inside_word"]
    assert result["black_seconds"] == 2
    assert result["audience_overlap"] is None
    assert normalize("Ça,") == "ca"
    assert union([(1, 2), (2, 3)]) == [(1, 3)]


def test_heatmap_union_and_reproducible_same_duration_baseline():
    heatmap = [{"start_time": i, "end_time": i + 1, "value": i} for i in range(10)]
    result = audience_overlap([(9, 10), (9, 10)], heatmap, 10)
    assert result["selected_fraction"] == 1
    assert 0 < result["random_same_duration_fraction"] < 0.1
    assert result == audience_overlap([(9, 10)], heatmap, 10)


@pytest.mark.parametrize(
    "change",
    [
        {"hook_0_3s": True},
        {"hook_0_3s": 5},
        {"publishable": 1},
        {"reasons": ["unknown"]},
        {"extra": 1},
        {"explanation": ""},
    ],
)
def test_judge_strict_closed_rubric(change):
    verdict = {
        "publishable": False,
        "hook_0_3s": 2,
        "reasons": ["fin_coupee"],
        "explanation": "Incomplete ending.",
    }
    with pytest.raises(ValueError):
        parse_verdict({**verdict, **change})


async def test_budget_counts_discarded_answers_and_blocks_before_http(tmp_path):
    budget = Budget(
        "0.05", tmp_path / "ledger.json", {"model": {"input": "0.000001", "output": "0.000001"}}
    )
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"usage": {"cost": 0.02}, "choices": []})

    # Bound includes 1,024 overhead tokens plus the declared output ceiling.
    body = {"model": "model", "messages": [], "max_tokens": 25000}
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with budget.intercept():
            await client.post("https://openrouter.ai/api/v1/chat/completions", json=body)
            await client.post("https://openrouter.ai/api/v1/chat/completions", json=body)
            with pytest.raises(BudgetExceeded):
                await client.post("https://openrouter.ai/api/v1/chat/completions", json=body)
    assert len(calls) == 2
    assert budget.committed == Decimal("0.04")
    assert [e["accounting"] for e in budget.entries] == ["provider_reported"] * 2 + [
        "blocked_before_send"
    ]


async def test_ambiguous_transport_keeps_asr_reservation(tmp_path):
    budget = Budget("0.02", tmp_path / "ledger.json", {})
    token = duration_context.set(60)

    def handler(request):
        raise httpx.ReadTimeout("unknown charge", request=request)

    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with budget.intercept(), pytest.raises(httpx.ReadTimeout):
                await client.post(
                    "https://api.openai.com/v1/audio/transcriptions", content=b"fixture"
                )
        assert budget.committed == Decimal("0.0061")
        assert budget.entries[0]["accounting"] == "uncertain_transport_upper_bound"
    finally:
        duration_context.reset(token)


def test_portable_review_contains_only_blind_data_and_escapes_transcript(tmp_path):
    source = tmp_path / "PRIVATE_SOURCE"
    source.mkdir()
    (source / "clip.mp4").write_bytes(b"fixture")
    (tmp_path / "report.json").write_text(
        json.dumps(
            {
                "run_id": "fixture",
                "sources": [
                    {
                        "source_id": "PRIVATE_SOURCE",
                        "clips": [
                            {
                                "idx": 0,
                                "media": "clip.mp4",
                                "title": "PRIVATE_TITLE",
                                "judge": {"publishable": True},
                                "score_total": 99,
                                "transcript_excerpt": "</script><script>alert(1)</script>",
                            }
                        ],
                    }
                ],
            }
        )
    )
    path = generate_review(tmp_path)
    html = path.read_text()
    assert "PRIVATE_SOURCE" not in html and "PRIVATE_TITLE" not in html
    assert "score_total" not in html and '"judge"' not in html
    assert "\\u003c/script>" in html
    assert len(list((path.parent / "clips").glob("*.mp4"))) == 1


async def test_openai_sdk_internal_retry_is_accounted(tmp_path):
    from openai import AsyncOpenAI

    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(
                500, json={"error": {"message": "temporary"}}, headers={"retry-after-ms": "1"}
            )
        return httpx.Response(200, json={"text": "Test", "duration": 70, "words": []})

    budget = Budget("0.10", tmp_path / "ledger.json", {})
    token = duration_context.set(70)
    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            async with AsyncOpenAI(api_key="offline", http_client=http, max_retries=1) as client:
                with budget.intercept():
                    await client.audio.transcriptions.create(
                        model="whisper-1",
                        file=("fixture.mp3", b"fixture", "audio/mpeg"),
                        response_format="verbose_json",
                    )
        assert len(calls) == 2
        assert budget.committed == Decimal("0.0141")
        assert budget.entries[0]["accounting"] == "missing_usage_upper_bound"
        assert budget.entries[1]["accounting"] == "asr_duration_tariff"
    finally:
        duration_context.reset(token)


async def test_provider_json_retry_accounts_for_discarded_paid_response(tmp_path, monkeypatch):
    from app.providers.openrouter import OpenRouterProvider

    calls = []

    def handler(request):
        calls.append(request)
        text = "Not JSON" if len(calls) == 1 else '{"ok":true}'
        return httpx.Response(
            200,
            json={
                "usage": {"cost": 0.001},
                "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
            },
        )

    provider = OpenRouterProvider()
    monkeypatch.setattr(
        provider,
        "_client",
        lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://openrouter.ai/api/v1"
        ),
    )
    budget = Budget(
        "0.10", tmp_path / "ledger.json", {"model": {"input": "0.000001", "output": "0.000001"}}
    )
    with budget.intercept():
        result = await provider.chat_json(
            model="model", system="Test", user="Test", max_tokens=4000
        )
    assert result.payload == {"ok": True}
    assert len(calls) == 2 and budget.committed == Decimal("0.002")


async def test_default_sdk_transport_cannot_bypass_budget(tmp_path):
    import importlib

    from openai import AsyncOpenAI

    calls = []
    async with AsyncOpenAI(api_key="offline", max_retries=0) as client:
        # Exercise the SDK's actual default HTTP implementation, not an injected
        # legacy client. Newer SDKs may use httpx2 while our adapter uses httpx.
        implementation = importlib.import_module(
            type(client._client).__mro__[2].__module__.split(".")[0]
        )

        def handler(request):
            calls.append(request)
            return implementation.Response(200, json={"text": "Test", "duration": 70, "words": []})

        client._client._transport = implementation.MockTransport(handler)
        budget = Budget("0.10", tmp_path / "ledger.json", {})
        token = duration_context.set(70)
        try:
            with budget.intercept():
                await client.audio.transcriptions.create(
                    model="whisper-1",
                    file=("fixture.mp3", b"fixture", "audio/mpeg"),
                    response_format="verbose_json",
                )
        finally:
            duration_context.reset(token)
    assert len(calls) == 1
    assert budget.committed == Decimal("0.0070")
    assert budget.entries[0]["stage"] == "transcription"


def test_prior_attempts_share_one_mission_cap(tmp_path):
    prior = [{"charged_or_reserved_usd": "0.04", "stage": "transcription"}]
    budget = Budget("0.05", tmp_path / "ledger.json", {}, prior)
    with pytest.raises(BudgetExceeded):
        budget.reserve("model", "text", Decimal("0.02"))
    assert budget.committed == Decimal("0.04")
