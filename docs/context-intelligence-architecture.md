# ClipFactory — Context Intelligence and Editorial Learning

Status: local architecture plus implemented provider-independent foundations.
This layer is not connected to `runner.py`, does not perform live research, and
cannot widen the authorised EDL scope.

## Local implementation checkpoint

The local worker now contains the complete non-production trust chain:

```text
bounded search/fetch contracts
  -> cited CampaignResearchPack
  -> signed source classifications + research quality audit
  -> bounded adaptive gap-repair plan
  -> tenant-authorised campaign/source/global vault snapshot
  -> mandatory question-specific retrieval
  -> exact-selection EditorialContextPack
  -> signed context issuance
  -> signature-reverified Director boundary
  -> cited Director 2.2 plan
  -> unchanged EDL compilation
  -> digest-only decision audit + signed render VariantProvenance
  -> preregistered experiments + provenance-bound outcomes
  -> signed complete promotion authority
  -> reviewed, expiring, scoped knowledge governance
```

The code remains deliberately split across small authority boundaries:

- `campaign_research.py`, `campaign_research_runtime.py` and
  `campaign_research_quality.py`, `campaign_research_strategy.py` and
  `research_attestation_authority.py` validate cited research, a
  DNS/peer-pinned injected runtime, signed source trust and bounded adaptive
  repair without a real provider;
- `knowledge_vault.py`, `knowledge_ingestion.py` and
  `knowledge_governance.py`, plus `knowledge_tenant_authority.py`, model
  storage, exact tenant-authorised snapshots, one-way materialisation and
  append-only promotion separately;
- `editorial_retrieval.py`, `editorial_context.py` and
  `context_intelligence.py` block contradictory constraints, then build one
  bounded projection from exactly the authorised retrieval result;
- `editorial_context_authority.py` issues the only normal Director capability;
  raw V2.2 prompt/parse/validate/compile entrypoints fail closed, while
  sensitive consumers reverify the signed envelope rather than trusting a
  private Python token;
- `vision_evidence_authority.py` binds verified candidate visuals to the exact
  asset, graph, source window, sampled-frame digests and ROI;
- `claim_authority.py` signs exact claim uses against context, plan and visual
  authority, without exposing claim text to the Director;
- `editorial_director_v22.py` validates decision citations before delegating
  unchanged controls to the existing compiler;
- `decision_provenance.py`, `decision_outcomes.py` and
  `learning_authority.py` bind snapshot, context issuance, decision audit,
  signed rendered variant, experiment arm and outcome, then require a
  short-lived signed recomputation of the complete gate before governance can
  promote policy;
- `knowledge_governance.py` records the verified promotion-authority digest in
  the append-only policy transition event.

No module above calls a live search engine, database, platform analytics API or
`runner.py`. HMAC helpers exercise the intended verification boundaries in
local tests; production still needs KMS-backed keys, ACLs, append-only storage,
rotation and revocation.

## Product thesis

ClipFactory's defensible advantage is not a larger prompt or a library of
editing tips. It is a traceable loop:

```text
evidence -> editorial hypothesis -> motivated decision -> rendered outcome
         -> measured observation -> reviewed learning -> scoped policy
```

Each arrow must remain inspectable. A useful system must be able to answer:

- what was observed in the source video;
- what came from campaign research or an approved campaign brief;
- which editing principle influenced a decision;
- why a particular beat, framing, effect or transition was selected;
- which outcome was measured, under which conditions;
- whether a later rule is based on one anecdote or repeated evidence.

This turns the Second Brain and Campaign Research into one context intelligence
system rather than two disconnected features.

## Four classes of truth

The system must never flatten all context into the same kind of "knowledge".

### 1. Source evidence

Observations tied to the current media asset:

- transcript words and sentence boundaries;
- source moments and narrative relations;
- verified faces, screens, objects, gestures and safe regions;
- measured silences, emphasis and energy changes;
- claims, proof, reactions and payoffs present in the video.

Source evidence is the only context class that can authorise what the edit says
or shows. Even then, word IDs remain the cut authority, verified visual regions
remain the framing authority, and licensed asset IDs remain the audio authority.

### 2. Campaign intelligence

Context specific to a campaign:

- the approved brief, offer, audience, CTA and prohibited topics;
- researched vocabulary, pains, objections and competitor positioning;
- approved claims and known proof assets;
- current hypotheses about hooks, angles and proof expectations.

Research can guide an angle or vocabulary choice. It cannot manufacture a fact
inside the source video and must never silently become an approved claim.

### 3. Editorial knowledge

Reusable global principles, techniques, patterns, problems, examples and
counterexamples. These notes explain or constrain a decision, but cannot emit a
timecode, file path, filter graph or unlicensed asset.

### 4. Outcome observations

Measurements attached to published variants:

- impressions and qualified plays;
- one-second and three-second retention;
- average watch time and percentage watched;
- completion and rewatch rate;
- CTA clicks, leads or conversions when available;
- negative signals such as hides, reports or unfollows;
- the platform, date window, spend/distribution conditions and sample size.

An outcome is an observation, not a universal editing rule. Raw view count alone
is especially weak because it mixes creative quality with distribution,
audience size, timing, paid spend and platform randomness.

## Separate epistemic state from lifecycle state

A single `status` field should not simultaneously describe what a note means,
how reliable it is and whether it is still active. The durable model should use
orthogonal fields.

```text
epistemic_kind: raw_source | observation | hypothesis | learning | policy
review_state:   unreviewed | approved | rejected
lifecycle:      active | superseded | deprecated
confidence:     calibrated score plus supporting sample metadata
```

The first local vault may retain the smaller status enum for simplicity, but
adapters and future persistence should preserve this conceptual separation.

### Promotion rules

Promotion is explicit and append-only:

```text
raw source
    -> observation
    -> hypothesis
    -> validated learning
    -> policy candidate
    -> curated policy
```

Each promotion creates a new version or note linked by `derived_from` and, when
appropriate, `supersedes`. Historical decisions continue to resolve the exact
version they originally cited.

Hard rules:

- web research enters the Campaign Vault only as an observation;
- a competitor statement is never an approved campaign claim by implication;
- one strong clip cannot promote a hypothesis to policy;
- a correlation between an edit and views cannot be called causal;
- contradictory evidence must remain linked and visible during review;
- a deprecated note is excluded from new context packs but remains auditable;
- policy promotion requires human approval until a later, separately reviewed
  governance system exists.

## Research Pack versus Campaign Vault

These artefacts have different jobs.

### CampaignResearchPack

A bounded, cited, expiring snapshot produced by one research policy. Every
finding references retained research sources. It is cacheable and replaceable.
It contains no long webpage bodies and is treated as hostile input even after
normalisation.

### Campaign Vault

The durable, versioned campaign memory. A one-way materialisation step converts
retained research findings into campaign observations. Approval, later learning
and policies happen in the vault, never inside the research pack.

```text
untrusted web evidence
      -> cited CampaignResearchPack
      -> campaign observation notes
      -> reviewed hypothesis or approved campaign knowledge
```

The distinction prevents a refreshed web search from overwriting a campaign's
approved language, and prevents a stale vault note from masquerading as current
market research.

## Finding semantics

Every research finding needs more than free text:

- stable finding ID;
- closed kind such as audience objection, vocabulary, expected proof or
  saturated claim;
- one or more retained source IDs;
- confidence and evidence class;
- time validity or an explicit unknown date;
- scope such as market, audience, platform and geography when known;
- optional contradiction or uncertainty markers.

Primary/official evidence can support factual market context. Community sources
are valuable for language, objections and lived experience, but should not be
silently upgraded to factual proof. Competitor sources describe positioning,
not the truth of their claims.

Negative evidence is first-class. A saturated claim, failed angle,
counterexample or contradictory source can be more useful to the Director than
another positive recommendation.

## The single downstream context boundary

Neither the raw vault nor the raw research pack should enter story selection or
the Director. Downstream models receive one bounded `EditorialContextPack`.

```text
Global Editing Vault --\
Campaign Vault ---------+-> authorised retrieval -> EditorialContextPack
Source Vault -----------/                         -> story/director prompt
```

The pack is a deterministic projection for one editorial question, campaign,
source graph and policy version. It is not a mutable chat memory.

Recommended initial budget:

- at most 3 global notes;
- at most 5 campaign notes;
- at most 4 source notes;
- at most 16 included relations;
- at most 240 characters of summary per note;
- at most 4,800 characters of canonical prompt JSON.

The exact numbers are policy, not hard-coded product truth, but every local test
must prove that the configured budget is enforced.

## Retrieval is a reasoning policy, not top-k similarity

Retrieval starts with a typed question:

```text
choose_hook | order_beats | repair_continuity | present_proof |
choose_framing | shape_cadence | place_effect | phrase_captions |
choose_payoff | choose_campaign_angle
```

The desired pack should contain complementary evidence, not twelve near-
duplicate notes:

1. applicable hard constraints or approved policy;
2. current source evidence;
3. campaign goal, objection or proof expectation;
4. one relevant editorial principle or technique;
5. an example, counterexample, risk or contradiction when available.

Candidates are filtered for tenant, campaign, source, status and question type
before ranking. Stable structured relevance beats non-deterministic model
intuition. A later semantic/vector score may improve recall, but cannot bypass
authorisation or dominate all diversity slots.

The context pack records why each note was selected: direct match, required
relation, counterexample, campaign constraint or source binding. This makes
retrieval itself debuggable.

## Reference namespaces

The word `source` is dangerously overloaded. IDs must make their authority
unambiguous:

- `research_source_ids`: retained external pages used to audit a research
  finding;
- `source_refs`: current-video notes or graph evidence bound to source moments,
  visual beats or audio beats;
- `campaign_refs`: authorised notes in the current campaign;
- `knowledge_refs`: authorised global editorial notes.

A URL or research source ID can never satisfy a shot's source evidence
requirement.

## Decision evidence contract

The existing Director schema 2.1 is closed and should remain stable. Citation
support belongs in an explicit future schema 2.2 rather than hidden optional
fields.

Conceptual shape:

```json
{
  "schema_version": "2.2",
  "campaign_hypothesis": "proof_first",
  "editorial_thesis": "Answer the main objection with visible proof",
  "decision_evidence": [
    {
      "decision_id": "plan",
      "knowledge_refs": ["global.pattern.claim_proof@2"],
      "campaign_refs": ["campaign.objection.results_not_real@1"],
      "source_refs": ["source.moment.conversion_proof@1"]
    },
    {
      "decision_id": "shot_proof",
      "knowledge_refs": ["global.principle.readable_proof_hold@3"],
      "campaign_refs": ["campaign.expected_proof.dashboard@1"],
      "source_refs": ["source.visual.dashboard_verified@1"]
    }
  ],
  "shots": []
}
```

Validation occurs before lowering to EDL 2.0:

- every returned reference is in the pack's allowlist;
- every campaign ref belongs to the current tenant and campaign;
- every shot-level source ref is bound to that shot's beat or source moment;
- global refs are active and at the permitted review/confidence level;
- refs are unique, versioned and from the correct namespace;
- missing required evidence fails closed;
- no ref can add words, milliseconds, paths, assets or render controls.

Knowledge citations should be required only when a decision actually invokes a
principle or technique. Forcing a citation on every trivial decision encourages
plausible but false references.

## Authority matrix

| Decision | Required authority | Context may influence | Context cannot do |
| --- | --- | --- | --- |
| Spoken cut | Transcript word IDs + EditScope | Narrative order and motivation | Emit seconds or widen scope |
| Visual proof | Verified candidate vision | Decide whether proof helps the angle | Treat research as on-screen proof |
| Screen framing | Verified readable ROI | Select `screen_focus` when useful | Invent or move an ROI |
| Music/SFX | Licensed asset registry | Choose an allowed mood/cue ID | Return a path or remote URL |
| Caption content | Compiled source words | Choose theme and phrase policy | Add researched claims as speech |
| Campaign angle | Campaign brief/vault | Prefer objection/proof/hook thesis | Rewrite absent source facts |
| Effect/transition | Closed EDL controls + evidence | Motivate emphasis or continuity repair | Generate arbitrary FFmpeg |

## Deterministic identity and invalidation

Every artefact needs both identity and audit timestamps. Volatile timestamps do
not belong in identity hashes.

### Research identity

Hash canonical relevant campaign fields plus research policy version. The
result changes when the audience, offer, niche, geography, platform, avoid list
or policy changes. A separate content digest covers normalized sources and
findings.

Refresh when:

- the campaign fingerprint changes;
- the research policy changes;
- the pack expires;
- a manual refresh is requested;
- a retained source is invalidated.

### Context identity

Hash:

- normalized question and retrieval policy version;
- campaign ID and campaign fingerprint;
- included note IDs and versions;
- research content digest when used;
- source graph digest and EditScope;
- editorial policy version.

Generated/accessed timestamps remain in audit metadata but outside the hash.

### Decision replay

Persist with a generated plan:

- context digest;
- exact note versions and decision references;
- research content digest;
- Director schema, prompt, model and policy versions;
- graph, transcript and asset-catalogue fingerprints;
- compiler and renderer versions;
- hypothesis and hook/proof/payoff beat IDs.

This is sufficient to explain a result and detect why a later replay differs.

## Learning from performance without teaching the wrong lesson

### Unit of observation

Performance belongs to a `PublishedVariantObservation`, not directly to a
principle. It records creative IDs, source/campaign/context fingerprints,
distribution conditions, metric definitions, sample size and measurement
window.

### Metric hierarchy

Use the metric closest to the decision being evaluated:

- hook decisions: qualified plays, one-second and three-second hold;
- pacing decisions: average percentage watched and drop-off around joints;
- payoff decisions: completion and post-payoff exits;
- replay devices: rewatch rate;
- campaign thesis: CTA click, lead or conversion when instrumented;
- all decisions: negative-feedback guardrails.

Views are useful for reach reporting but weak as the sole creative learning
target.

### Comparability

Variant comparisons should record whether they share:

- source material and candidate scope;
- campaign and audience;
- publishing window and platform;
- organic versus paid distribution;
- account baseline and approximate exposure.

Without randomised delivery, ClipFactory should call the result directional,
not causal.

### Promotion threshold

A hypothesis may become a validated learning only after repeated, sufficiently
exposed observations across more than one source or publication context, with
no severe guardrail regression. The exact statistical threshold is policy and
must be configurable. The local `OutcomeStatPolicy` now closes that threshold:
it versions and digests the per-arm minimum denominator, minimum independent
experiments, minimum absolute lift and preregistered metrics. The gate
recomputes a two-sided 95% Newcombe/Wilson interval from raw outcomes and
rejects small samples, an interval containing zero, a mismatched point
estimate or an unregistered metric. Its digest is signed in the short-lived
promotion authority; legacy diagnostics remain readable but cannot be signed.

A policy candidate additionally needs:

- a declared scope: platform, format, niche, audience and content conditions;
- the action it recommends and the risk it mitigates;
- supporting observations and counterevidence;
- known exceptions;
- review owner and expiry/review date.

## Experiments and variants

Three variants should represent different theses, not cosmetic effect swaps.

```text
proof_first          -> show credible evidence early
objection_first      -> articulate and answer resistance
curiosity_first      -> open a loop, then resolve it
authority_first      -> establish credible expertise
transformation_first -> lead with before/after change
```

Each thesis must be supported by real campaign and source refs. The variant
audit should preserve existing structural diversity checks and add:

- distinct supporting campaign observations;
- explicit expected metric and failure condition;
- shared versus changed variables;
- a reason the source contains enough proof for the thesis;
- no use of an unsupported hypothesis merely to fill a set of three.

When only one or two hypotheses are grounded, render one or two strong variants
rather than manufacture a third.

## Security and tenancy

Authorisation occurs before search, traversal, prompt construction and returned
reference resolution. Looking up an ID first and checking ownership later is a
data leak.

Rules:

- global notes contain no private customer content;
- campaign notes are scoped by owner and campaign;
- source notes are scoped by owner, campaign and source asset;
- any non-global base vault needs an exact signed owner/campaign/source
  authority before snapshot composition; the snapshot and later context
  issuance both bind that authority digest;
- returned LLM refs resolve only against the current pack allowlist;
- Markdown, titles, snippets and summaries are always fenced as data;
- external URLs are audit refs, never navigation instructions to the Director;
- synthesis-provided source labels have no authority: only the signed
  classification set accepted by the consumer can unlock `trusted_complete`;
- archived research observations are not active evidence unless their exact IDs
  are re-materialized from the currently bound research digest;
- a `verified_candidate` enum alone cannot unlock privileged framing; signed
  asset/frame/window/ROI evidence is required;
- an `approved` claim dataclass alone cannot unlock copy or overlays; exact
  usages are signed and reverified against the plan and context;
- research fetching later must revalidate DNS and every redirect, reject local
  and private ranges, and enforce MIME, byte and time limits;
- prompt injection text can be retained as quoted evidence only when safe and
  cannot alter the output schema or tool policy.

## Failure behavior

The ordinary approved campaign brief remains the fallback when research is
missing, partial, expired or rejected. Missing global knowledge should reduce
explanation richness, not stop an otherwise grounded cut. Missing source
evidence must fail any decision that depends on it.

Examples:

- no research: use the approved brief, mark research digest absent;
- no campaign-specific note: do not invent an objection-first hypothesis;
- no verified visual proof: keep spoken proof or choose another source beat;
- unsigned source classifications: treat the pack as untrusted/limited, never
  inherit `official` or `primary` from synthesis;
- stale research note present in the vault but absent from the active lineage:
  archive it and exclude it from retrieval;
- unsigned operator claim: do not render an overlay;
- context budget exceeded: deterministically prune lowest-priority evidence;
- contradictory high-priority policies: reject and request review;
- unknown or cross-campaign ref: reject the plan before EDL compilation.

## Evaluation plan

### Contract tests

- every research finding has known retained citations;
- materialised research notes remain observations;
- cross-tenant, cross-campaign and cross-source reads fail;
- unknown relations and references fail;
- deprecated notes are excluded by default;
- hostile content stays inert and bounded;
- identical inputs produce byte-identical canonical packs and digests;
- cache identity changes for every relevant policy/input version;
- context cannot widen EditScope or introduce timecodes;
- Director evidence refs bind to the selected beat and source moment.

### Retrieval evaluation

Create editorial questions with expected supporting and contradicting refs.
Measure:

- authorisation precision: always 100%;
- citation validity: always 100%;
- source-binding validity: always 100%;
- deterministic replay: always 100%;
- budget compliance: always 100%;
- useful coverage and counterexample inclusion on labelled fixtures;
- duplicate-note rate and irrelevant-context rate.

### Editorial evaluation

On retained local media, compare blinded variants with and without the context
layer for:

- campaign relevance;
- hook clarity;
- claim/proof coherence;
- visual proof readability;
- continuity and pacing;
- caption phrasing;
- payoff completion;
- traceability of every non-trivial decision.

This stage tests editorial quality, not public view count.

### Performance evaluation

Only after publication instrumentation exists, compare matched variants and
report uncertainty, distribution conditions and guardrails. Context-supported
editing is successful when it improves the targeted metric reliably enough to
justify cost and complexity, not merely when one clip goes viral.

## Local implementation sequence and state

### Lot C1 — pure foundations — implemented locally

- cited, versioned `CampaignResearchPack` with hostile validation;
- pure source-quality audit, signed source-classification envelope and bounded
  adaptive gap planner;
- vault notes, relations, retrieval and bounded context projection;
- no network, database, provider or runner integration.

### Lot C2 — materialisation and unified context — implemented locally

- one-way research finding to Campaign Vault observation adapter;
- source graph to Source Vault ref adapter;
- exact tenant-vault authority for every non-global base snapshot;
- exact active-research lineage separate from archived observations;
- mandatory retrieval with contradiction blocking;
- stable `EditorialContextPack` containing the exact retrieval selections;
- tenant/campaign/source isolation tests.

### Lot C3 — cited Director — implemented locally

- preserve schema 2.1;
- introduce explicit schema 2.2 with decision evidence refs;
- require a signed `VerifiedEditorialContext` capability for prompt, parse,
  validation and compile; signed-only wrappers and sensitive consumers recheck
  the envelope rather than treating a module-private token as authority;
- validate refs against the exact context pack before lowering unchanged EDL
  controls to the existing compiler;
- require signed asset/frame/ROI evidence for privileged visual framing and a
  signed claim-use envelope for any source, research or operator claim path;
- prove byte-equivalent EDL output for equivalent 2.1 and 2.2 edit controls.

### Lot C4 — local comparative previews — partially implemented

- generate grounded hypotheses from one retained source/campaign fixture;
- render only hypotheses with sufficient source evidence;
- compare context-on versus context-off decisions and contact sheets;
- inspect decision audit, captions, proof holds and render timing.

### Lot C5 — adapters behind feature flags — not activated

- bounded search/fetch client and persistent cache;
- database/object-storage representation and strict tenant policies;
- optional story-selection and Director context seams;
- explicit feature flag, cost and latency instrumentation;
- still no automatic policy promotion.

### Lot C6 — outcome learning — pure contracts implemented, adapters pending

- versioned publication/metric observations;
- exact decision-audit → variant → experiment-arm → outcome provenance;
- matched-variant aggregation and confidence reporting;
- closed, signed `OutcomeStatPolicy` with Newcombe/Wilson uncertainty gate;
- signed complete promotion authority; legacy diagnostic artefacts cannot be
  signed or promoted;
- reviewed learning and policy workflow with authority digest in its event;
- rollback, supersession and expiry.

## Definition of done before production activation

- all context and reference boundaries fail closed;
- every non-trivial Director decision is explainable from authorised refs;
- context never changes timing or asset authority;
- research retry/failure cannot break rendering;
- cached research and packs are reproducible by version/digest;
- local context-on previews are editorially better in blind review;
- cost and latency are measured by stage;
- campaign/source data cannot cross tenants;
- the existing V2 render, caption and QC suite remains green;
- activation is reviewed explicitly and remains reversible.

## Product consequence

The Second Brain provides durable editorial memory. Campaign Research provides
fresh but untrusted market evidence. The Context Pack makes both usable under a
strict budget. The Director cites the evidence behind its choices. Outcome
observations can then improve scoped policies without turning a lucky view spike
into doctrine.

That closed, inspectable loop is the product: ClipFactory learns how to edit for
a campaign while preserving what is true in the source and what is safe to
execute.
