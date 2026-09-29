# ClipFactory Editor Brain V3 — local architecture

Date: 2026-08-09  
Status: local design and test build; not connected to `runner.py`

## Outcome we are targeting

Editor V2 already gives a model a safe editing grammar and compiles exact
transcript word boundaries into a frame-authoritative FFmpeg timeline. The next
quality step is not a larger effects catalogue. It is an evidence layer that
lets the director reason about **why** a cut exists and whether the spoken idea,
picture, sound and campaign promise remain coherent after that cut.

The target pipeline is:

```text
transcript words + sentences
        +
scene / face / screen / motion observations
        +
silence / emphasis / loudness observations
        +
campaign goal and candidate scope
        |
        v
EditorialBeatGraph (evidence, IDs, relationships and risks)
        |
        v
LLM director (three distinct theses, motivated decisions only)
        |
        v
semantic compiler and editorial QC
        |
        v
existing word-ID EDL compiler -> captions -> FFmpeg renderer
        |
        v
low-resolution preview critic -> at most one bounded repair
```

The transcript remains the authority for spoken boundaries. Vision and audio
observations constrain editorial choices but never become free-form FFmpeg
timecodes emitted by the model.

## What the current build actually knows

The existing local V2 path has strong execution guarantees:

- exact inclusive word ranges, arbitrary ordering and replay;
- frame-authoritative video, audio and caption timing;
- closed framing/effect/transition/caption catalogues;
- trusted audio asset IDs and deterministic rendering;
- basic QC for opening/final roles, required/protected ranges, caption coverage,
  effect density and cut density.

Its understanding inputs are still too coarse for senior-editor decisions:

- `VideoMap` describes 15–60 second events, not the gesture, screen state or
  camera change at a proposed cut;
- deep vision aggregates several stills into one face position, energy and
  visual score per segment;
- `AudioMap` measures silence and loudness but does not align emphasis,
  respiration and phrase intent on one editorial timeline;
- the edit prompt receives transcript words, a coarse candidate and optional
  untyped asset/hint dictionaries, not a shared narrative/visual/audio model;
- editorial QC measures structure and density but cannot prove that one shot
  answers the previous one, that a visual proof is readable, or that a cut lands
  on a meaningful phrase boundary.

This explains the current review renders: they are technically clean and
expressive, but a screen may be present without being readable, a face crop may
change without a visual reason, and captions may form balanced word counts
without forming a natural phrase.

## The evidence contract

`EditorialBeatGraph` is a provider-independent, immutable artefact built inside
an explicit `EditScope`. Every record has a stable ID and source provenance.

### Source moments

A source moment is the smallest useful spoken unit, normally a transcript
sentence or a bounded part of one.

Required fields:

- inclusive `from_word_id` and `to_word_id`;
- source window derived from those words;
- closed semantic role: `claim`, `question`, `setup`, `constraint`, `contrast`,
  `proof`, `reveal`, `reaction`, `payoff`, `cta` or `unknown`;
- entity and antecedent references when supplied by semantic analysis;
- proof requirement: `none`, `spoken`, `visible` or `both`;
- salience and confidence with explicit provenance.

Semantic analysis may label or connect these moments, but it cannot expand the
word range outside the compiler-owned edit scope.

### Visual beats

A visual beat is a measured source window with a closed description:

- `talking_head`, `reaction`, `screen_proof`, `object_proof`, `demo`, `broll`,
  `scene_change` or `unknown`;
- primary/multiple/no/unknown face state and a coarse face-centre bucket;
- screen readability, motion class and caption-safe zone;
- an optional normalized proof/subject region of interest backed by observed
  frames, so a later crop can enlarge the useful dashboard or object instead of
  merely centring the whole landscape source;
- evidence source and confidence.

The first implementation can project existing `VideoMap`/deep-vision evidence.
Later, candidate-only local CV can make face, scene and motion boundaries finer
without running vision on every source frame.

### Audio beats

An audio beat is measured evidence bounded by transcript words:

- `speech`, `micro_pause`, `dramatic_pause`, `dead_air`, `emphasis`, `impact` or
  `unknown`;
- left/right word IDs, source window and energy bucket;
- classification reason and evidence source.

Silence is never removed merely because it is quiet. A bounded silence can be a
candidate `dead_air`; a semantic policy may protect it as a dramatic pause.

### Editorial beats and edges

An editorial beat joins one source moment to its overlapping visual/audio
evidence. Its closed purpose is `hook`, `orient`, `escalate`, `prove`, `release`,
`payoff` or `cta`.

Edges represent valid editorial relations:

- `answers`, `proves`, `contrasts`, `causes`, `escalates`, `reframes`, `repeats`
  or `continues`;
- semantic, visual and audio continuity flags;
- risks such as `orphan_reference`, `time_jump`, `same_scale_jump`,
  `ambient_jump`, `mid_thought_cut` or `proof_missing`;
- a closed set of allowed repairs.

The graph describes possible edits. It does not choose the final order and it
does not replace the EDL compiler.

## The director contract

The next edit-intent schema should reference beat IDs while retaining exact
word-ID subranges. Every shot and every joint must declare its motivation using
a closed vocabulary:

- entry: `open_loop`, `answer`, `proof_reveal`, `reaction`, `pace_up`,
  `time_compress`, `context_reset`;
- exit: `semantic_completion`, `question_hold`, `proof_hold`, `impact`,
  `escalation`, `cta`;
- joint: `continue`, `answer`, `reveal`, `contrast`, `time_compress`,
  `pattern_interrupt`, `reaction`;
- continuity strategy: `natural`, `match_action`, `match_gaze`, `audio_lcut`,
  `hard_jump`, `reset_with_caption`;
- effect reason: `emphasis`, `reveal`, `impact` or `none`.

Free-form explanations remain useful for logs and review, but only IDs and
closed fields can authorize compilation or rendering.

The semantic compiler must verify that:

1. referenced beats and word ranges exist inside `EditScope`;
2. required/protected words remain intact;
3. a visible-proof obligation overlaps readable proof evidence for a minimum
   hold duration;
4. every non-continuous joint has a valid motivation and permitted repair;
5. framing is compatible with observed face/screen state;
6. effects are both within budget and attached to an editorial reason;
7. the final plan still compiles through the existing V2 EDL boundary.

## Human editor reflexes to encode

These are testable rules rather than prompt advice:

1. Do not open on an orphan connector, pronoun or unnamed referent.
2. Prefer a sentence edge, measured pause, gesture boundary or camera change for
   a cut; otherwise require an explicit `pace_up` or `impact` motivation.
3. Do not place two short, same-scale talking-head shots back to back without a
   justified jump-cut strategy.
4. When speech promises a number, result or demonstration, follow the relevant
   `answers`/`proves` edge and show readable evidence when required.
5. Hold screen proof long enough to read it; mere presence in a sampled frame is
   insufficient. A `screen_focus` decision also needs a trusted proof region;
   otherwise use a full-frame proof layout or reject the crop.
6. Do not zoom, flash, shake or add SFX unless the effect is anchored to a word
   and has a compatible reason.
7. Preserve reaction frames and intentional silence around a punchline or
   reveal; remove only evidence-backed dead air.
8. Build captions from semantic phrases and sentence/pause boundaries, then
   apply visual length limits. Never make word count the primary grouping rule.
9. Use a pacing curve: dense opening, enough orientation to understand, a
   controlled breath before proof/payoff, and a clean ending.
10. Prefer the least stylized transition that communicates the intended
    relationship. A hard cut remains the default.

## Variants and learning

Generating three files is not enough. Variants must differ in editorial
hypothesis:

- different hook beat, payoff beat or edge relation;
- bounded source overlap and structural similarity;
- an explicit campaign hypothesis such as proof-first, curiosity-first or
  authority-first;
- stable variant and policy IDs persisted with the future production artefact.

Views cannot be guaranteed. The learning loop should compare qualified metrics
per hypothesis: 1/3-second hold, average percentage watched, completion,
rewatch, shares/saves and the campaign CTA. Raw views are distribution-dependent
and must not train the editor in isolation.

## Performance budget

The understanding layer should remain cheaper than brute-force video analysis:

1. Reuse transcript words/sentences and global scene-change timestamps.
2. Build coarse graph evidence once and persist/cache it by source checksum and
   analysis-version hash.
3. Run finer face/screen/motion/audio analysis only inside candidate scopes plus
   a small boundary margin.
4. Decode each candidate window once and reuse its observations across all
   variants.
5. Render low-resolution previews for editorial criticism; render 1080×1920
   only after plan/QC approval.
6. Permit at most one closed repair pass to avoid uncontrolled model and render
   loops.

## Local implementation sequence

### Implemented local checkpoint — 2026-08-09

The following pieces now exist and pass the full local worker suite:

- immutable `EditorialBeatGraph` with scoped source moments, verified visual
  provenance, audio pauses, graph relations and prompt-safe IDs;
- deterministic editorial-reflex QC for proof presence/hold, exact ROI
  propagation, same-scale jumps, sentence boundaries, source-window leakage,
  stylized transitions and globally protected dramatic pauses;
- schema 2.1 motivated Director with beat references, closed entry/exit/joint
  reasons, word-anchored effects, explicit replay/context-reset/time-compression
  paths and lowering into the existing frame-authoritative EDL 2.0 compiler;
- deterministic three-variant diversity checks for campaign hypothesis,
  opening beat, timeline structure and source overlap;
- sentence-aware captions when ASR sentence evidence exists, with conservative
  fallback when it does not;
- scoped pre/post-roll clamping that may retain silence but never neighbouring
  speech outside the selected word authority;
- real ROI-aware FFmpeg proof composition: crop the verified source region,
  fit it without distortion, and overlay it on a blurred vertical background.

Validation at this checkpoint: `369 passed`, Ruff clean, Python compilation
clean and `git diff --check` clean. A retained real-source preview renders in
2.26 seconds for 18.50 seconds of output (realtime factor about 0.12), with
30 fps video and 48 kHz stereo audio both exactly 18.50 seconds.

This checkpoint is still local-only. The retained fixture has no sentence
segments and no automatic candidate-vision ROI, so its benchmark harness uses
one manually verified stable ROI to demonstrate the renderer. Candidate-only
vision, automatic phrase evidence, preview criticism and production persistence
remain Lots C/D. Nothing is wired into `runner.py`.

### Lot A — evidence and reflexes

- add the pure `editorial_beats.py` graph contract and deterministic builders;
- add graph validation, provenance and prompt-safe serialization;
- add optional graph-aware editorial QC for phrase boundaries, joint risk and
  proof obligations;
- add fixtures for orphan hooks, missing proof, protected pauses, redundant
  same-scale jump cuts and readable proof holds.

No provider, FFmpeg, database or `runner.py` change is required.

### Lot B — director schema 2.1

- expose only scoped graph records to the editing model;
- parse beat references and closed motivations defensively;
- compile semantic intent into the existing `EditIntentPlan`/`CompiledEDL`;
- generate three structurally distinct plans and reject near-duplicates.

### Lot C — candidate-only multimodal precision

- refine shot boundaries, face tracks, screen readability, motion and audio
  emphasis inside selected scopes;
- derive dynamic framing tracks and semantic caption phrases;
- validate proof hold and caption safe zones on actual preview frames.

### Lot D — bounded preview critic and product learning

- critique the rendered preview rather than only the JSON plan;
- accept one closed `RevisionRequest`, recompile and re-run QC;
- persist graph, plan, render, QC, policy and variant attribution;
- feature-flag a small A/B batch only after local visual approval and existing
  V2 trust-boundary blockers are closed.

## Acceptance gate before production wiring

- every rendered word occurrence is covered by a validated graph moment;
- zero unknown beat/asset/word references reach the renderer;
- zero unmotivated non-continuous cuts;
- all visible-proof obligations have readable overlapping evidence and a
  minimum hold;
- all required/protected phrases survive compilation;
- semantic caption cues do not cross sentence or protected-pause boundaries;
- variant diversity is measured and enforced;
- preview QC and final stream-level A/V checks pass;
- the existing renderer trust, edit-scope, audio provenance/licensing and legacy
  fail-open blockers are closed before any `runner.py` activation.

Until this gate passes, Editor V3 remains a local review path.
