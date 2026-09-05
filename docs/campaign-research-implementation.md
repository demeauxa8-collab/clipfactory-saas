# Campaign Research Pack — implementation brief

Date: 2026-08-09
Status: local foundation implemented and tested; no live provider, database or
production-runner integration yet

Combined context, decision-provenance and governed-learning architecture:
[`context-intelligence-architecture.md`](context-intelligence-architecture.md).

## Goal

Give clip selection and the Editor Brain reliable market context about the
campaign: audience language, pains, objections, expected proof, competitor
angles and saturated claims.

Research must run as a separate, cached campaign stage. The editing model must
**not browse the web during every montage**. This keeps renders reproducible,
limits cost and reduces prompt-injection exposure.

```text
campaign created or updated
        -> four typed discovery requirements
        -> scoped web research
        -> cited CampaignResearchPack
        -> signed independent source classifications + quality audit
        -> at most two gap-repair queries when evidence is limited
        -> Campaign Vault observation notes
        -> question-specific authorised retrieval
        -> bounded EditorialContextPack
        -> story/candidate selection
        -> Editor Brain / variant theses
        -> deterministic EDL and render
```

## Current production gap

The worker currently loads only:

- campaign name;
- audience;
- niche;
- tone;
- goal;
- avoided topics;
- example hooks.

Story selection uses that brief, but no Internet research is performed. The
local V2 editing director receives the selected candidate and transcript, not a
full campaign-research artefact.

## Implemented artefact

The local build now has a versioned, serializable `CampaignResearchPack`. Web
content is untrusted evidence; only normalized findings and retained source
references can leave the research boundary.

```python
@dataclass(frozen=True)
class CampaignResearchSource:
    schema_version: Literal["1.0"]
    source_id: str
    url: str
    title: str
    publisher: str | None
    published_at: str | None
    accessed_at: str
    source_type: Literal[
        "official", "competitor", "industry", "community", "platform"
    ]
    evidence_tier: Literal["primary", "secondary", "community"]
    evidence_summary: str

@dataclass(frozen=True)
class CitedFinding:
    schema_version: Literal["1.0"]
    finding_id: str
    kind: Literal["fact", "vocabulary", "hypothesis", "negative_evidence"]
    scope: Literal["market_context", "sampled_sources"]
    text: str
    source_ids: tuple[str, ...]
    confidence: float
    valid_from: str
    valid_until: str

@dataclass(frozen=True)
class CampaignResearchPack:
    schema_version: Literal["1.0"]
    research_policy_version: str
    campaign_fingerprint: str
    generated_at: str
    expires_at: str
    status: Literal["complete", "partial", "unavailable"]
    market_summary: CitedFinding | None
    sections: tuple[CampaignResearchSection, ...]
    sources: tuple[CampaignResearchSource, ...]
    confidence: float
```

Every finding must cite one or more retained `source_id` values. Facts and
negative evidence cannot be supported only by community sources. Full webpages,
search snippets and long copied passages are not part of the pack.

The provider-independent runtime is also implemented. It plans 4–6 bounded
queries, injects search/fetch/synthesis/cache clients, binds every HTTP hop to
both its public DNS answers and the public peer IP actually joined, strips
active HTML and prompt fences, passes only a normalized text projection to one
synthesis call, and returns `unavailable` on unsafe or incompatible output. No
concrete network client was added; the future adapter must obtain
`FetchHop.connected_ip` from the transport socket, not from a second DNS lookup.

`campaign_research_quality.py` adds a separate, content-blind trust audit. A
synthesis model cannot certify its own source as official or primary. The
public classification dataclass is audit data only. A trusted adapter or human
must issue a short-lived HMAC envelope which binds the exact tenant, campaign,
research digest, source IDs, URL digests, source classes and independent
publisher/domain groups. `prepare_editorial_context`, the adaptive planner and
the Context authority reverify that envelope with their own verifier; importing
a private Python token or supplying a raw tuple is not accepted.

A pack reaches `trusted_complete` only with fresh, independently classified
evidence, critical-section coverage, triangulated facts (or a verified official
primary source) and supported contrary evidence. A pack that merely declares
`status=complete` is refused without that current signed quality chain.

`campaign_research_strategy.py` turns the audit into a bounded adaptive plan.
It begins with four typed requirements — audience language, expected proof,
competitor/negative evidence and platform-native hook context — then groups all
remaining critical gaps into no more than two repair queries. The hard total is
six queries. Exact private hook examples, avoid-topic wording, URLs, emails and
long token-like values are never copied into queries.

## Research workflow

1. Sanitize the campaign brief and build four typed discovery queries.
2. Search for audience language, problems, objections, proof expectations,
   competitor positioning and current platform context.
3. Prefer official and primary sources for factual claims. Community sources can
   inform vocabulary or objections but must be labelled accordingly.
4. Fetch only an allowlisted number of results per query and impose response,
   character, token and time budgets.
5. Normalize the evidence into the closed schema above.
6. Validate URLs, timestamps, field lengths, source references and confidence.
7. Classify retained sources through the signed adapter/human authority and run
   the content-blind quality audit.
8. If evidence is limited, emit at most two deterministic gap-repair queries;
   never repeat research inside a render retry.
9. Persist/cache the pack by campaign fingerprint and research-policy version.
10. Reuse it for every clip and variant until it expires or the campaign changes.

Suggested initial budget:

- 4–6 queries per campaign;
- 3–5 useful sources per query before deduplication;
- 8–15 retained sources in the final pack;
- one synthesis call;
- no research call inside FFmpeg/render retries;
- manual refresh plus a conservative expiry, for example 14–30 days.

## Research as an evidence-coverage loop

The planner does not equate more pages with better research. It tracks a closed
set of requirements and asks four questions about each one:

- is the required section covered at all;
- is the evidence current enough for its policy;
- is it independent, or are several URLs controlled by the same publisher or
  registered domain;
- is there credible contrary or negative evidence, rather than only confirming
  material.

This produces explicit `ResearchGap` objects. Repair queries are grouped by
missing critical coverage and systemic trust gaps, so the two-query repair
budget can address the whole audit instead of spending itself on the first two
alphabetical findings. A trusted pack stops after discovery; a blocked or
unavailable pack falls back rather than repeatedly searching.

Source diversity is evaluated as a graph of shared editor/domain ownership, not
as a count of hostnames. Three subdomains or syndicated copies therefore remain
one evidence component. A factual claim needs triangulation across independent
components unless an authenticated official-primary source supplies the narrow
fact directly.

Cache identity is layered:

1. campaign fingerprint + research-policy version for discovery;
2. canonical research content digest for the immutable pack;
3. signed classification/audit digest for trust at a specific time.

Changing campaign inputs, policy, retained content or source classifications
invalidates the corresponding layer without rewriting historical packs already
cited by rendered variants.

## Pipeline integration

### Story selection

Extend the campaign context supplied to `story_arc_user_prompt()` with a compact
research section:

- what the audience wants or fears;
- which proof it finds credible;
- useful native vocabulary;
- overused claims to avoid;
- campaign-specific angles and objections.

Research should affect campaign fit, hook register and payoff selection. It must
not override transcript evidence or manufacture facts absent from the video.

### Editor Brain / V2 director

Do not pass the research pack directly to the Director. Materialize retained
findings as `observation` notes in the Campaign Vault, then retrieve the small,
authorised subset needed for the current editorial question into one
`EditorialContextPack`. Require each variant to state a closed campaign
hypothesis, such as:

- `proof_first`;
- `objection_first`;
- `curiosity_first`;
- `authority_first`;
- `transformation_first`.

The director still selects source words and graph beat IDs. Research never
produces FFmpeg seconds, file paths, filters or unverified on-screen claims.
Archived research notes may remain in the durable vault, but retrieval can use
only the exact `active_research_note_ids` materialized from the currently bound
research digest. Findings from `claims_requiring_verification` are excluded
until a separately signed claim-evidence workflow resolves them.

### Ranking and learning

Persist these identifiers with each future variant:

- campaign research version/fingerprint;
- editorial policy version;
- hypothesis type;
- external `research_source_ids` supporting the campaign observation;
- current-video `source_refs` supporting the actual edit (a distinct namespace);
- hook/proof/payoff beat IDs.

This allows performance metrics to determine whether a research-backed angle
helped retention or CTA results without pretending that research guarantees
views.

## Security and reliability rules

- Treat every webpage, result title, snippet and competitor claim as untrusted
  data and fence it from system instructions.
- Never expose API keys, private campaign data or customer transcripts in search
  queries.
- Block private/local network URLs and non-HTTP(S) schemes; protect against SSRF
  and redirects to private ranges.
- Use bounded downloads, MIME checks, timeouts and size limits.
- Strip scripts/active markup, neutralize prompt-fence markers, and pass only a
  bounded plain-text projection inside a synthesis prompt that treats every
  source sentence as untrusted data. Do not rely on brittle semantic detection
  of phrases such as “ignore previous instructions”.
- Materialize findings as typed `untrusted_external_research_data` records;
  use the same non-truncating projector in retrieval and direct context builds.
- Never trust `source_type` or `evidence_tier` emitted by synthesis as source
  authority; bind production classifications to a signed independent
  classification envelope and reverify it at every sensitive consumer.
- Preserve source URLs and access dates for auditability.
- Fail gracefully to the ordinary campaign brief when research is unavailable.
- Do not state researched claims as facts in captions unless they are also
  supported by the source video or an explicitly approved overlay workflow.

## Local code placement

Start local and provider-independent:

```text
apps/worker/app/pipeline/campaign_research.py
apps/worker/app/pipeline/campaign_research_runtime.py
apps/worker/app/pipeline/campaign_research_quality.py
apps/worker/app/pipeline/campaign_research_strategy.py
apps/worker/app/pipeline/research_attestation_authority.py
apps/worker/tests/test_campaign_research.py
apps/worker/tests/test_campaign_research_runtime.py
apps/worker/tests/test_campaign_research_quality.py
apps/worker/tests/test_campaign_research_strategy.py
apps/worker/tests/test_research_attestation_authority.py
```

Keep three boundaries separate:

1. `CampaignResearchClient`: search/fetch adapter;
2. pure parser/validator for hostile or incomplete results;
3. pure prompt serializer that emits a compact, source-referenced context.

Do not connect this first patch to `runner.py`. Build and test the contract,
then integrate it behind an explicit feature flag after review.

## Minimum tests

- campaign fingerprint changes when relevant campaign fields change;
- unchanged campaign reuses the cached pack;
- unknown fields, oversized content and broken source references are rejected;
- prompt-injection text stays data and cannot alter the output contract;
- private/local URLs and unsupported schemes are rejected;
- duplicate URLs and near-identical findings are deduplicated;
- missing/failed research falls back to the original brief;
- prompt serialization respects strict size and source-count limits;
- story/director context contains audience, objections and expected proof but no
  raw webpage body;
- no research is triggered during a render retry.

## Remaining implementation order

1. Implement a concrete HTTP/search provider adapter behind the tested runtime
   contracts, with transport-peer DNS pinning, KMS-backed source-classification
   signing and secret management.
2. Add a persistent cache keyed by campaign fingerprint and research policy.
3. Generate one real pack for human source-by-source review; do not use live
   research during render retries.
4. Compare locally rendered context-on/context-off variants and decision audits.
5. Add story-selection and Director seams behind an explicit feature flag only
   after the local editorial review.
6. Instrument latency/cost, tenant policies and source revocation before any
   production activation.

This feature should improve campaign relevance and editorial judgment. It is a
context layer, not a substitute for transcript/visual evidence and not a promise
of view count.
