"""Run the retained source through the selector and verified Director 2.2."""

from __future__ import annotations

import asyncio
import copy
import json
import secrets
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from full_stack_benchmark import (
    ROOT,
    SOURCE,
    AuditedProvider,
    get_settings,
    inputs,
    read,
    save,
)

from app.models import ArcSegmentSpec, SegmentVision, StoryArc, VideoEvent, VideoMap, VisionResult
from app.pipeline.audio_map import AudioMap, LoudnessPoint, SilenceInterval
from app.pipeline.boundaries import (
    MAX_CLIP_SECONDS,
    MAX_SEGMENT_SECONDS,
    MIN_CLIP_SECONDS,
    MIN_SEGMENT_SECONDS,
    anchor_arcs_to_transcript,
    filter_arcs_by_duration,
    snap_arc_segments,
)
from app.pipeline.campaign_research import parse_campaign_research_pack
from app.pipeline.clip_render import prepare_candidate_edit, render_prepared_candidate
from app.pipeline.context_intelligence import prepare_editorial_context
from app.pipeline.decision_provenance import (
    materialize_director_decision_provenance,
)
from app.pipeline.editor_v2 import PreparedV2Edit
from app.pipeline.editorial_beats import build_editorial_beat_graph
from app.pipeline.editorial_context import EditorialQuestion
from app.pipeline.editorial_context_authority import (
    HMACSHA256Authority,
    issue_editorial_context,
    verify_editorial_context_capability,
)
from app.pipeline.editorial_director_v22 import EDITORIAL_DIRECTOR_V22_SYSTEM_PROMPT
from app.pipeline.editorial_knowledge import load_editorial_retention_vault
from app.pipeline.editorial_qc import EditorialQCPolicy, evaluate_editorial_qc
from app.pipeline.editorial_reflex_qc import evaluate_editorial_reflex_qc
from app.pipeline.edl import EditScope, InclusiveWordRange
from app.pipeline.edl_captions import build_caption_plan
from app.pipeline.knowledge_tenant_authority import (
    HMACSHA256TenantAuthority,
    issue_tenant_vault_authority,
)
from app.pipeline.score import preselect_arcs_for_vision, rank_and_pick, score_arc
from app.pipeline.verify import verify_arcs
from app.pipeline.vision import deep_vision_for_arc


def now():
    return datetime.now(UTC).isoformat()


async def main():
    fixture, transcript = inputs()
    provider, settings = AuditedProvider(timeout_seconds=120), get_settings()
    arcs = [
        StoryArc(**{**a, "segments": [ArcSegmentSpec(**s) for s in a["segments"]]})
        for a in read("fresh_arcs.json")["arcs"]
    ]
    anchored, anchor_report = anchor_arcs_to_transcript(arcs, transcript, strict=True)
    verified_arcs, rejected = verify_arcs(transcript, anchored)
    snapped, snap_report = snap_arc_segments(
        verified_arcs,
        transcript.words,
        sentences=transcript.sentences,
        safe_padding=True,
        min_duration_seconds=MIN_SEGMENT_SECONDS,
        max_duration_seconds=MAX_SEGMENT_SECONDS,
    )
    usable, duration_report = filter_arcs_by_duration(
        snapped,
        min_segment_seconds=MIN_SEGMENT_SECONDS,
        max_segment_seconds=MAX_SEGMENT_SECONDS,
        min_clip_seconds=MIN_CLIP_SECONDS,
        max_clip_seconds=MAX_CLIP_SECONDS,
    )
    selected, diversity_rejections = preselect_arcs_for_vision(usable, 3)
    save(
        "selection-audit.json",
        dict(
            anchor=asdict(anchor_report),
            verification=rejected,
            snap=asdict(snap_report),
            duration=asdict(duration_report),
            diversity=diversity_rejections,
            selected=[asdict(a) for a in selected],
        ),
    )
    print("Selected for paired comparison:", len(selected), flush=True)
    candidates = []
    for i, arc in enumerate(selected):
        path = f"deep-vision-{i}.json"
        if not (ROOT / path).exists():
            directory = ROOT / "deep_frames"
            directory.mkdir(exist_ok=True)
            per_segment, frames, tokens = await deep_vision_for_arc(
                provider=provider,
                model=settings.primary_vision_deep_model,
                source_path=str(SOURCE),
                arc=arc,
                workdir=str(directory),
                arc_idx=i,
            )
            save(
                path, dict(segments=[asdict(s) for s in per_segment], frames=frames, tokens=tokens)
            )
        per_segment = [
            SegmentVision(**{**s, "vision": VisionResult(**s["vision"]) if s["vision"] else None})
            for s in read(path)["segments"]
        ]
        opening = " ".join(
            w.word
            for w in transcript.words
            if arc.segments[0].start <= w.start < arc.segments[0].start + 3
        )
        candidate = score_arc(
            arc=arc,
            per_segment_vision=per_segment,
            campaign=fixture["campaign"],
            opening_text=opening,
        )
        candidate.vision_per_segment = per_segment
        candidates.append(candidate)
    candidates = rank_and_pick(candidates, len(candidates))
    save("shared-candidates.json", [asdict(c) for c in candidates])
    vm_raw, audio_raw = read("video_map.json"), read("audio_map.json")
    vm = VideoMap(vm_raw["summary"], [VideoEvent(**v) for v in vm_raw["events"]])
    audio = AudioMap(
        **{
            **audio_raw,
            "silences": tuple(SilenceInterval(**s) for s in audio_raw["silences"]),
            "loudness_points": tuple(LoudnessPoint(**s) for s in audio_raw["loudness_points"]),
        }
    )
    results = []
    for i, candidate in enumerate(candidates):
        row = {"index": i, "title": candidate.title, "selector_score": candidate.score_total}
        results.append(row)
        print("Rendering candidate", i, candidate.title, flush=True)
        # Both arms retain the entire source frame. Deep vision is used for
        # candidate scoring; no un-attested face position becomes crop authority.
        for arm in ("selector", "director_final"):
            prefix = f"{arm}/clip_{i:02d}"
            try:
                if (ROOT / f"{prefix}.manifest.json").exists():
                    row[arm] = {
                        "status": "delivered",
                        "manifest": str(ROOT / f"{prefix}.manifest.json"),
                        "video": str(ROOT / f"{prefix}.mp4"),
                        "resumed": True,
                    }
                    continue
                if arm == "selector":
                    prepared = prepare_candidate_edit(
                        copy.deepcopy(candidate),
                        transcript,
                        source_duration_seconds=595.220,
                        framings=[("fit_blur", 0.5)] * len(candidate.segments),
                    )
                else:
                    prepared = await direct(
                        candidate, transcript, vm, audio, fixture, provider, settings, prefix
                    )
                delivered = await render_prepared_candidate(
                    prepared=prepared,
                    source=str(SOURCE),
                    transcript=transcript,
                    out_path=str(ROOT / f"{prefix}.mp4"),
                    source_sha256=read("inputs.json")["source_sha256"],
                )
                row[arm] = {
                    "status": "delivered",
                    "manifest": delivered.manifest_path,
                    "video": delivered.output_path,
                    "duration": delivered.rendered_duration_seconds,
                    "qc": asdict(delivered.quality),
                }
            except Exception as exc:
                import traceback

                traceback.print_exc()
                row[arm] = {"status": "rejected", "error": str(exc), "type": type(exc).__name__}
            save("comparison.json", results)
    print(json.dumps(results, ensure_ascii=False), flush=True)


async def direct(candidate, transcript, vm, audio, fixture, provider, settings, prefix):
    # Expand only to enclosing ASR sentence boundaries, at most eight seconds
    # per edge. The baseline keeps the original selector windows for attribution.
    expanded = copy.deepcopy(candidate)
    for segment in expanded.segments:
        for sentence in transcript.sentences:
            if (
                sentence.start <= segment.start < sentence.end
                and segment.start - sentence.start <= 8
            ):
                segment.start = sentence.start
            if sentence.start < segment.end <= sentence.end and sentence.end - segment.end <= 8:
                segment.end = sentence.end
        segment.start = max(0, segment.start - 4)
        segment.end = min(595.220, segment.end + 4)
    allowed = []
    for segment in expanded.segments:
        ids = [
            i
            for i, w in enumerate(transcript.words)
            if w.end > segment.start and w.start < segment.end
        ]
        allowed.append(InclusiveWordRange(ids[0], ids[-1]))
    graph = build_editorial_beat_graph(
        transcript=transcript,
        scope=EditScope(tuple(allowed)),
        candidate=expanded,
        video_map=vm,
        audio_map=audio,
    )
    save(f"{prefix}.graph.json", asdict(graph))
    campaign_id = str(uuid5(NAMESPACE_URL, json.dumps(fixture["campaign"], sort_keys=True)))
    source_id = fixture["job_id"]
    vault = load_editorial_retention_vault()
    instant = datetime.now(UTC)
    expiry = instant + timedelta(hours=6)
    tenant_signer = HMACSHA256TenantAuthority("local_benchmark_tenant", secrets.token_bytes(32))
    tenant = issue_tenant_vault_authority(
        vault,
        owner_id="local_benchmark",
        campaign_id=campaign_id,
        source_id=source_id,
        signer=tenant_signer,
        issued_at=instant,
        expires_at=expiry,
        authority_id="benchmark_tenant",
    )
    question = EditorialQuestion(
        "variant",
        campaign_id,
        source_id,
        tuple(b.beat_id for b in graph.editorial_beats),
        tuple(m.moment_id for m in graph.source_moments),
        (
            "Create a clear hook, source-backed tension, progressive proof and a "
            "complete payoff for: " + (candidate.title or "")
        )[:160],
    )
    research = parse_campaign_research_pack(read("research/pack.json"))
    context = prepare_editorial_context(
        base_vault=vault,
        campaign=fixture["campaign"],
        graph=graph,
        question=question,
        owner_id="local_benchmark",
        revision="benchmark_r1",
        editorial_policy_version="1.0",
        as_of=instant,
        tenant_authority=tenant,
        tenant_authority_verifier=tenant_signer,
        research_pack=research,
    )
    save(f"{prefix}.context.json", json.loads(context.context.to_prompt_json()))
    authority_research = research if research.status != "unavailable" else None
    signer = HMACSHA256Authority("local_benchmark_context", secrets.token_bytes(32))
    issued = issue_editorial_context(
        context.snapshot,
        context.context,
        graph,
        signer=signer,
        issued_at=instant.isoformat(),
        expires_at=expiry.isoformat(),
        issuance_id="benchmark_context",
        tenant_authority=tenant,
        tenant_authority_verifier=tenant_signer,
        research_pack=authority_research,
    )
    verified = verify_editorial_context_capability(
        issued,
        context.snapshot,
        context.context,
        graph,
        verifier=signer,
        now=now(),
        expected_owner_id="local_benchmark",
        expected_campaign_id=campaign_id,
        expected_source_id=source_id,
        research_pack=authority_research,
    )
    save(
        f"{prefix}.authority.json",
        {
            "issued": issued.unsigned_payload(),
            "ephemeral_local_signer": True,
            "research_status": context.research_status,
        },
    )
    prompt = verified.prompt(transcript=transcript, target_duration_seconds=40, now=now())
    prompt += (
        "\nKeep complete sentences and a natural ending. Use only available source_safe framing, "
    )
    prompt += (
        "speed 1 and no music or SFX assets. You may trim within the supplied moments to repair "
    )
    prompt += (
        "dependent openings or unfinished endings. Do not add claims. Output only schema 2.2 JSON."
    )
    if len(candidate.segments) == 1:
        prompt += (
            "\nCONTINUOUS CLIP CONTRACT: output exactly ONE shot. Choose its first and last "
            "spoken words to make a complete standalone thought in 12 to 60 seconds. "
            "Use shot_id=continuous, beat_id=beat_00, role=hook, entry_motivation=scroll_stop, "
            "exit_motivation=continue, joint_motivation=opening, continuity_strategy=establish, "
            "effects=[], transition_out=hard_cut, framing={mode:source_safe,center_x:0.5,"
            "base_scale:1}, speed=1, pre_roll_ms=0, post_roll_ms=0. These are the controls "
            "allowed for this continuous beat; do not subdivide or replay it. "
            "Keep decision_evidence at root with plan and continuous records. "
            "Avoid an unexplained opening such as fait cette video or D'ailleurs. "
            "End on a completed assertion, before trailing Et, Donc, Et la ici, or a new "
            "unfinished sentence. Preserve the small-sample qualification for conversion rates. "
            "ASR segments may contain several sentences: select the appropriate word IDs, "
            "not automatically the outermost words of the moment."
        )
    prompt += (
        "\nASR sentence text (observational context, only word IDs authorize cuts): "
        + json.dumps(
            [
                asdict(s)
                for s in transcript.sentences
                if any(s.start < r.end and s.end > r.start for r in expanded.segments)
            ],
            ensure_ascii=False,
        )
    )
    (ROOT / f"{prefix}.prompt.txt").write_text(prompt)
    error = None
    for attempt in range(2):
        response_path = f"{prefix}.attempt{attempt}.json"
        if (ROOT / response_path).exists():
            payload = read(response_path)
        else:
            response = await provider.chat_json(
                model=settings.primary_text_model,
                system=EDITORIAL_DIRECTOR_V22_SYSTEM_PROMPT,
                user=prompt,
                max_tokens=6000,
                temperature=0.2,
            )
            payload = response.payload
            save(response_path, payload)
        try:
            plan = verified.parse(payload, now=now())
            edl = verified.compile(plan, transcript, now=now(), source_duration_ms=595220)
            qc = evaluate_editorial_qc(
                edl,
                transcript,
                policy=EditorialQCPolicy(
                    final_roles=frozenset({"hook", "payoff", "cta"}),
                    weak_opening_tokens=frozenset(),
                ),
            )
            reflex = evaluate_editorial_reflex_qc(edl, graph, transcript=transcript)
            save(
                f"{prefix}.attempt{attempt}.qc.json",
                {"editorial": asdict(qc), "reflex": asdict(reflex)},
            )
            if qc.status != "pass" or reflex.status != "pass":
                raise ValueError(
                    "QC requires repair: "
                    + json.dumps({"editorial": asdict(qc), "reflex": asdict(reflex)})
                )
            if not 12 <= edl.duration_ms / 1000 <= 60:
                raise ValueError("Clip duration must be 12 to 60 seconds")
            provenance = materialize_director_decision_provenance(
                plan,
                verified=verified,
                now=now(),
                variant_id=prefix.replace("/", "_"),
                created_at=now(),
            )
            save(f"{prefix}.provenance.json", provenance.to_payload())
            save(f"{prefix}.accepted-plan.json", payload)
            return PreparedV2Edit(edl, qc, build_caption_plan(edl, transcript))
        except Exception as exc:
            error = exc
            save(
                f"{prefix}.attempt{attempt}.error.json",
                {"type": type(exc).__name__, "error": str(exc)},
            )
            prompt += (
                "\nYour previous plan was rejected. Correct this exact error "
                "without changing the source facts: "
            )
            prompt += str(exc) + "\nPrevious plan: " + json.dumps(payload, ensure_ascii=False)
    raise ValueError(f"Director rejected after two attempts: {error}")


if __name__ == "__main__":
    asyncio.run(main())
