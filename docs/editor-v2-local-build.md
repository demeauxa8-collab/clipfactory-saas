# ClipFactory Editor V2 — local review build

Date: 2026-08-08  
Status: local-only, not wired into the production worker runner

## Outcome

The local V2 path can turn a closed, word-addressed edit decision list (EDL)
into one deterministic FFmpeg render. The model controls editorial choices;
the compiler owns validation, exact frames, trusted assets and execution.

This build deliberately does **not** replace the legacy `runner.py` path. It is
intended for local review before any production integration, staging, commit or
push.

## What the model can control

- exact inclusive transcript word ranges for every shot;
- arbitrary shot order, source replay and non-contiguous micro-cuts;
- per-shot constant speed in the validated range;
- per-shot framing from a closed catalogue;
- caption theme per shot;
- word-anchored effects: `punch_in`, `zoom_out`, `freeze`, `flash`, `shake`,
  `blur` and `color_pop`;
- duration-preserving transitions: `hard_cut`, `time_jump`, `reveal`,
  `contrast` and `hard_impact`;
- music and SFX by trusted catalogue ID only, with bounded gains and closed
  ducking presets.

The model cannot pass filesystem paths, URLs, shell fragments, arbitrary
FFmpeg filters or unbounded numeric values.

## Execution contract

1. `edit_intent.py` asks for one structured EDL from the allowed transcript
   ranges and optional audio-map hints.
2. `edl.py` validates the vocabulary and compiles word ranges into a
   frame-authoritative timeline.
3. `editorial_qc.py` rejects incoherent hooks, missing proof/payoff, protected
   phrase loss, excessive cuts/effects and weak caption coverage.
4. `edl_captions.py` derives captions from compiled word occurrences, including
   replayed words, and balances cue sizes to avoid orphan one-word tails.
5. `audio_render_plan.py` resolves music/SFX IDs through a local manifest with
   licence, checksum, root-confinement and gain checks.
6. `edl_render.py` lowers all shots, framing, effects and transitions into one
   duration-preserving filter graph.
7. `ffmpeg.py` performs one final encode and validates frame count, A/V drift,
   48 kHz stereo audio and mux duration.
8. `editor_v2.py` rejects excessive black-frame output before returning the
   local result.

## Final local renders

Source fixture:

`/Users/augustindemeaux/clipfactory-data/bench/source/2221f645-ed0e-47b2-8201-417d7c517a39/source.mp4`

Output directory:

`/Users/augustindemeaux/clipfactory-data/bench/results/codex-edl-v2-2026-08-08-final/`

| Variant | Editorial angle | Duration | Frames | Render wall time |
|---|---|---:|---:|---:|
| `proof_first` | sale, conversion proof, profit, CTA | 23.167 s | 695 | 6.50 s |
| `curiosity` | risk question, reveal, proof, comment CTA | 18.900 s | 567 | 5.55 s |
| `creator_led` | authority, promise, profit, follow CTA | 22.533 s | 676 | 6.18 s |

All three are 1080×1920, 30 fps, H.264, AAC 48 kHz stereo. The final strict
black-frame scan found no interval of 20 ms or longer. Visual source/output
checks confirmed the selected source ranges and all internal joins.

## Validation

Final local suite:

```text
369 passed
ruff: all checks passed
git diff --check: clean
```

The reviewed state also includes a regression test proving that an explicit
start-word anchor applies sub-50 ms corrections instead of being marked as
resolved while retaining the coarse timestamp.

Targeted tests also cover real FFmpeg rendering, silent source fallback,
non-linear replay, exact word occurrences, hostile EDL rejection, captions,
audio-map analysis, trusted asset resolution, music ducking/SFX mixing and
stream-level duration checks.

## Intentional limitations before production activation

- The V2 is not called by `runner.py`; there is no production fallback or job
  persistence contract for it yet.
- The real review clips contain no music because no approved licensed asset
  manifest was supplied. The secure asset path and a synthetic end-to-end mix
  are implemented and tested.
- `follow_primary_face` is not yet a temporal face tracker. Reliable dynamic
  reframing needs a vision-derived shot/face track rather than a single static
  crop.
- `screen_focus` now accepts a verified normalized source ROI and really crops
  that proof before fitting it over a blurred vertical canvas. The graph-aware
  Director never supplies this mode without one unique readable candidate ROI;
  the legacy no-ROI preset remains compatible only for old local EDLs.
- `pip_proof` and true variable `speed_ramp` are rejected explicitly until the
  schema can reserve a second visual source and source-time keyframes.
- Transcript text remains the caption authority. ASR mistakes such as a missing
  percent sign must be corrected by a separate evidence-backed transcript
  normalization pass, not silently invented by the renderer.
- View count cannot be guaranteed by rendering. Shipping should add variant
  attribution and retention metrics (3-second hold, average watch percentage,
  completion, rewatch, shares and qualified CTA) so editorial policies learn
  from real performance.

## Next production gate

After local visual approval, add a feature-flagged runner integration with an
explicit legacy fallback, persist the EDL/render/QC artefacts, provision a
licensed audio manifest, then run a small A/B batch before making V2 the
default.
