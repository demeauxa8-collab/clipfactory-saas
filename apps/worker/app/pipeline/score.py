from __future__ import annotations

import difflib
import re
import unicodedata
from collections.abc import Iterable
from typing import Any

import structlog

from ..models import (
    MontageCandidate,
    MontageSegment,
    SegmentVision,
    StoryArc,
    VisionResult,
)

log = structlog.get_logger()

# Montage-v2 weights. Multi-segment clips are first-class now, so the mix leans on
# campaign fit and payoff strength alongside watchability and a first-2-seconds
# hook. The LLM's self-reported retention stays discounted. Weights sum to 1.0.
ARC_WEIGHTS = {
    "visual_proof": 0.28,
    "hook_strength": 0.20,
    "payoff_strength": 0.18,
    "campaign_fit": 0.12,
    "editing_continuity": 0.12,
    "retention": 0.10,
}

# A clip with no visible person anywhere is almost always weak b-roll for a
# creator video — multiply the final score down hard.
NO_PERSON_PENALTY = 0.55

# A clip the selector itself flags as needing outside context cannot work in a
# feed: the viewer has no "previous five minutes". The flag is parsed upstream,
# so honour it instead of storing it and looking away.
NOT_SELF_CONTAINED_PENALTY = 20

# Fuzzy keyword match threshold — tolerates typos in the brief ("buinesse"
# ~= "business") without matching unrelated words.
_FUZZY_RATIO = 0.8

# Stricter threshold for avoid-topics: a false positive there silently kills a
# good clip, so we only tolerate inflections (truqués ~= truqué) and not
# neighbouring lemmas ("nuire" must not match "nuit").
_AVOID_FUZZY_RATIO = 0.9

# ---------------------------------------------------------------------------
# Diversity (MMR) tuning
# ---------------------------------------------------------------------------
# rank_and_pick is not a top-N any more. Shipping three clips carved out of the
# same passage is the worst thing we can deliver ("you sold me the same clip
# three times"), so each round picks the candidate that maximises
#   score x (1 - MMR_LAMBDA * redundancy_with_already_picked)
# and outright drops anything above MMR_DUPLICATE_CUTOFF.
#
# Trade-off: the cutoff means we may return FEWER clips than target_clip_count
# when the arcs all cover the same ground. That is deliberate — 2 distinct clips
# beat 3 clips where one is a rerun. The best-scoring candidate is always kept,
# so we never return an empty batch when candidates exist.
MMR_LAMBDA = 0.85

# Redundancy above this is treated as a duplicate and removed from the batch.
MMR_DUPLICATE_CUTOFF = 0.9

# Temporal Jaccard (on the union of a clip's source windows) at or above this is
# already "the same passage" -> redundancy saturates at 1.0, i.e. eliminatory.
TEMPORAL_OVERLAP_HARD = 0.5

# Title/excerpt similarity below this is just shared vocabulary from the same
# speaker, not a repeated story — ignore it.
TEXT_SIMILARITY_FLOOR = 0.55

# Cap the text compared per candidate: SequenceMatcher is O(n^2).
_REDUNDANCY_TEXT_CHARS = 400


def joint_compatibility(a: VisionResult | None, b: VisionResult | None) -> str:
    """Classify the cut between two adjacent segments, for the renderer to pick a
    transition. 'continuous' = same decor AND same person visibility (a natural
    hard cut); 'scene_change' = anything else (needs an intentional transition,
    or one side has no vision)."""
    if a is None or b is None:
        return "scene_change"
    if a.decor == b.decor and a.person_visible == b.person_visible:
        return "continuous"
    return "scene_change"


def _fuzzy_contains(keyword: str, words: set[str], ratio: float = _FUZZY_RATIO) -> bool:
    """True if any word in the text closely matches the keyword (typo-tolerant)."""
    return any(
        difflib.SequenceMatcher(None, keyword, w).ratio() >= ratio for w in words
    )


# Letters only: briefs are noisy ("- Interdits :", "buinesse,") and digits carry
# no topical meaning on the brief side.
_TOKEN_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

_MIN_KEYWORD_LEN = 4

# Words a brief uses to describe the deliverable or to glue a sentence together.
# They must never count as topical overlap, and never as an avoided subject.
_BRIEF_STOPWORDS = frozenset(
    {
        # function words long enough to pass the length filter
        "avec", "sans", "pour", "dans", "chez", "cette", "leur", "leurs",
        "mais", "donc", "alors", "comme", "plus", "moins", "tout", "tous",
        "toute", "toutes", "etre", "être", "avoir", "faire", "fait", "cela",
        "elle", "elles", "nous", "vous", "votre", "notre", "tres", "très",
        "bien", "aussi", "encore", "trop", "juste", "peut", "pouvant", "doit",
        "quelque", "quelques", "autre", "autres", "meme", "même", "ainsi",
        # brief boilerplate: the deliverable, not the subject
        "clip", "clips", "video", "vidéo", "videos", "vidéos", "contenu",
        "contenus", "creer", "créer", "creez", "créez", "cree", "crée",
        "faites", "montrer", "montre", "extrait", "extraits", "moment",
        "moments", "sujet", "sujets", "chose", "choses", "type", "genre",
        "style", "public", "cible",
    }
)

# Labels a human puts in front of an avoid entry. "- Interdits : x" must be
# read as "x", otherwise the substring never matches anything.
_AVOID_LABELS = frozenset(
    {
        "interdit", "interdits", "interdite", "interdites", "interdiction",
        "eviter", "éviter", "evite", "évite", "evites", "avoid", "exclure",
        "exclu", "exclus", "banni", "bannis", "proscrit", "proscrits",
        "attention", "regle", "règle", "regles", "règles", "contrainte",
        "contraintes", "note", "notes", "important", "tabou", "tabous",
        "ne", "pas", "non", "jamais", "a", "à", "de", "du", "des", "les", "le",
        "la", "et", "ou",
    }
)

# Leading bullets / numbering an operator pastes from a doc. The escapes are
# en dash, em dash, bullet, middle dot and a non-breaking space.
_BULLET_CHARS = "-*>#0123456789.)( \t\u2013\u2014\u2022\u00b7\u00a0"

# Penalty applied when an avoid topic is fully recognised in the clip.
AVOID_PENALTY = 25
# A multi-word avoid only bites once at least half of its significant words are
# there; the penalty then scales with that coverage.
AVOID_MIN_COVERAGE = 0.5
# One messy brief must not zero the fit on its own.
AVOID_PENALTY_CAP = 50

# Keyword bonuses. The goal carries the commercial intent ("acheter sa
# formation"), so a goal hit is worth slightly more than an audience/niche hit.
KEYWORD_BONUS = 4
GOAL_KEYWORD_BONUS = 5
# Cap the keyword half so a keyword-stuffed brief cannot saturate the score and
# drown the LLM's own judgement.
KEYWORD_BONUS_CAP = 28


def _significant_words(text: str) -> list[str]:
    """Topical words of a brief field: >= 4 letters, no boilerplate, deduped,
    order preserved."""
    out: list[str] = []
    seen: set[str] = set()
    for word in _TOKEN_RE.findall(text.lower()):
        if len(word) < _MIN_KEYWORD_LEN or word in _BRIEF_STOPWORDS or word in seen:
            continue
        seen.add(word)
        out.append(word)
    return out


def _avoid_terms(entry: str) -> list[str]:
    """Turn one (possibly filthy) avoid_topics entry into significant words.

    "- Interdits : détournements moqueurs" -> ["détournements", "moqueurs"]
    An entry that boils down to a label only yields [] and never penalises.
    """
    cleaned = (entry or "").strip().lstrip(_BULLET_CHARS).strip()
    if ":" in cleaned:
        head, _, tail = cleaned.partition(":")
        head_tokens = _TOKEN_RE.findall(head.lower())
        # Only drop the head when it is pure labelling ("Interdits", "A eviter").
        if head_tokens and all(t in _AVOID_LABELS for t in head_tokens):
            cleaned = tail
    return _significant_words(cleaned)


def _clip_text(arc: StoryArc) -> str:
    return " ".join(
        [
            arc.title or "",
            arc.viral_reason or "",
            arc.suggested_hook or "",
            *[s.transcript_excerpt or "" for s in arc.segments],
        ]
    ).lower()


def _keyword_fit_score(arc: StoryArc, campaign: dict[str, Any]) -> int:
    """Fuzzy overlap with audience + niche + goal, minus a sanitised avoid-list
    penalty. Baseline 60 (neutral: we know nothing either way)."""
    fit = 60
    words = set(_TOKEN_RE.findall(_clip_text(arc)))

    bonus = 0
    seen: set[str] = set()
    fields = (
        (campaign.get("audience") or "", KEYWORD_BONUS),
        (campaign.get("niche") or "", KEYWORD_BONUS),
        # The goal is what the clip must actually push the viewer towards.
        (campaign.get("goal") or "", GOAL_KEYWORD_BONUS),
    )
    for raw, points in fields:
        for keyword in _significant_words(str(raw)):
            if keyword in seen:
                continue
            seen.add(keyword)
            if _fuzzy_contains(keyword, words):
                bonus = min(KEYWORD_BONUS_CAP, bonus + points)
    fit = min(100, fit + bonus)

    penalty = 0
    for avoid in campaign.get("avoid_topics") or []:
        terms = _avoid_terms(str(avoid or ""))
        if not terms:
            continue  # label-only / empty entry: never penalise
        matched = sum(
            1 for term in terms if _fuzzy_contains(term, words, _AVOID_FUZZY_RATIO)
        )
        coverage = matched / len(terms)
        if coverage >= AVOID_MIN_COVERAGE:
            penalty = min(AVOID_PENALTY_CAP, penalty + round(AVOID_PENALTY * coverage))
    fit = max(0, fit - penalty)

    return fit


def _campaign_fit_score(arc: StoryArc, campaign: dict[str, Any]) -> int:
    """Blend the LLM's campaign-fit self-report with a fuzzy keyword overlap.
    Falls back to a neutral 60 for the LLM half when it did not report a value."""
    keyword_fit = _keyword_fit_score(arc, campaign)
    llm = arc.campaign_fit_llm if arc.campaign_fit_llm is not None else 60
    return max(0, min(100, round(0.5 * llm + 0.5 * keyword_fit)))


def _editing_continuity_score(arc: StoryArc, per_segment_vision: list[SegmentVision]) -> int:
    """Higher = cleaner to cut. Instead of punishing every extra segment, we score
    each JOINT by how compatible the two adjacent segments look."""
    base = 100
    if arc.continuity_risk == "high":
        base -= 35
    elif arc.continuity_risk == "medium":
        base -= 15

    # Per-joint continuity: a hard cut between two visually identical scenes is
    # cheap; a scene change is a real (but manageable) transition; a missing
    # vision leaves us blind, so it sits between the two.
    visions_by_idx = {sv.segment_idx: sv.vision for sv in per_segment_vision}
    for i in range(len(arc.segments) - 1):
        a = visions_by_idx.get(i)
        b = visions_by_idx.get(i + 1)
        if a is None or b is None:
            base -= 6
        elif joint_compatibility(a, b) == "continuous":
            base -= 3
        else:
            base -= 8

    for sv in per_segment_vision:
        if sv.vision is None:
            continue
        if "no face" in sv.vision.problems:
            base -= 12
        if "dark" in sv.vision.problems:
            base -= 5
        if "unreadable slide" in sv.vision.problems:
            base -= 3

    return max(0, min(100, base))


# A clip that names the line it lands on has an actual ending; one that leaves
# payoff_line empty is usually a moment that trails off. The bigger half of the
# bonus is only paid when that line is really inside the last segment the model
# submitted — the field alone is a promise, the overlap is a check.
PAYOFF_LINE_BONUS = 6
PAYOFF_LINE_IN_LAST_SEGMENT_BONUS = 6


def _payoff_line_bonus(arc: StoryArc) -> int:
    """Reward a stated payoff line, more so when it sits in the last segment."""
    raw: Any = getattr(arc, "payoff_line", None)
    if not isinstance(raw, str) or not raw.strip():
        return 0
    bonus = PAYOFF_LINE_BONUS
    last = arc.segments[-1] if arc.segments else None
    excerpt = _normalize_text(last.transcript_excerpt if last is not None else "")
    line = _normalize_text(raw)
    if line and excerpt and line in excerpt:
        bonus += PAYOFF_LINE_IN_LAST_SEGMENT_BONUS
    return bonus


def _payoff_strength(arc: StoryArc, per_segment_vision: list[SegmentVision]) -> int:
    """Strength of the last segment's payoff. Uses LLM signals + last-segment vision."""
    base = arc.estimated_retention or 60
    if per_segment_vision:
        last = per_segment_vision[-1].vision
        if last is not None:
            if last.energy >= 70:
                base += 10
            if last.visual_score >= 70:
                base += 5
    base += _payoff_line_bonus(arc)
    return max(0, min(100, base))


# Charged words: they make a promise, a stake or a taboo explicit in the first
# breath. Matched as substrings, so prefixes cover inflections ("choqu" ->
# choqué/choquant). Keep every entry >= 4 chars: shorter ones ("fou") hide
# inside ordinary words ("fournir") and fire at random.
_HOOK_CHARGED_WORDS = (
    "jamais", "personne", "secret", "arnaque", "garanti", "gratuit",
    "impossible", "choqu", "incroyable", "interdit", "erreur", "piège",
    "piege", "mensonge", "vérité", "verite", "faillite", "ruiné", "ruine",
    "perdu", "perte", "gagné", "gagne", "explosé", "explose", "arrêtez",
    "arretez", "stop", "tout le monde", "la plupart",
)

# A number in the opening is the cheapest proof a viewer can parse in 1 second.
_HOOK_DIGIT_RE = re.compile(r"\d")
_HOOK_MONEY_RE = re.compile(
    r"[€$£%]|\b(?:euros?|dollars?|pourcents?|pourcentage|mille|milliers?|"
    r"millions?|milliards?|centaines?|dizaines?)\b"
)

# Question openers, checked on the first tokens only (whisper gives us no "?").
_HOOK_QUESTION_WORDS = (
    "pourquoi", "comment", "combien", "est-ce", "qu'est", "quand", "quel",
    "quelle", "quels", "quelles", "saviez", "savais", "devinez",
)

# ---------------------------------------------------------------------------
# Banned openers — SINGLE SOURCE OF TRUTH
# ---------------------------------------------------------------------------
# Wind-ups and orphan connectors a clip must never open on: the viewer has
# already scrolled by the time the sentence gets going. `app.prompts` renders
# these very tuples into the arc-selection prompt (BANNED_OPENERS_FOR_PROMPT),
# so the rule the model is given and the penalty measured here cannot drift
# apart — they had: "vu que" was forbidden but unpunished, "puisque" punished
# but never forbidden.
# Matching folds accents, so no unaccented duplicates are needed here.
BANNED_OPENER_WORDS: tuple[str, ...] = (
    "et", "mais", "donc", "alors", "puis", "car", "ensuite", "après", "enfin",
    "voilà", "bref", "bon", "ben", "euh", "or", "puisque", "genre",
)
BANNED_OPENER_PHRASES: tuple[str, ...] = (
    "parce que", "vu que", "du coup", "en fait", "en vrai", "en plus",
    "par contre", "par exemple", "d'ailleurs", "c'est-à-dire", "c'est à dire",
    "comme je disais", "je disais", "je te disais", "je vous disais",
)

# Exactly what the prompt shows the model.
BANNED_OPENERS_FOR_PROMPT = " / ".join((*BANNED_OPENER_WORDS, *BANNED_OPENER_PHRASES))

# How much of the clip's first words we look at.
_OPENING_CHARS = 140

# A connector one or two words in still means the clip opens on a fragment, so
# banned PHRASES are searched across this many leading tokens. Single banned
# words stay pinned to the very first token: "moi et mon associé" is a fine
# opening, "et moi mon associé" is not.
_WEAK_LEAD_IN_SCAN_TOKENS = 4

WEAK_OPENING_PENALTY = 15

# The hook is judged on what is really audible in this much of the clip's first
# segment. The caller reads those words off the timestamped transcript and hands
# them over — see score_arc(opening_text=...).
HOOK_OPENING_WINDOW_SECONDS = 2.5

_WS_RE = re.compile(r"\s+")


def _normalize_text(text: str) -> str:
    return _WS_RE.sub(" ", (text or "").replace("\u2019", "'").lower()).strip()


def _fold_accents(text: str) -> str:
    """'après' -> 'apres'. Whisper and the models disagree on accents; the ban
    list must not."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c)
    )


_BANNED_OPENER_WORDS_FOLDED = frozenset(_fold_accents(w) for w in BANNED_OPENER_WORDS)
_BANNED_OPENER_PHRASES_FOLDED = tuple(_fold_accents(p) for p in BANNED_OPENER_PHRASES)


def _opening_text(arc: StoryArc, opening_text: str | None = None) -> str:
    """The clip's very first words.

    `opening_text` is what the viewer REALLY hears — read off the timestamped
    transcript by the caller — and it always wins: a model that declares clean
    opening_words while the tape says "en fait…" must not escape the penalty.
    Without it we fall back to the declared opening_words, then to the head of
    the first segment's excerpt.
    """
    raw: Any = opening_text
    if not isinstance(raw, str) or not raw.strip():
        raw = getattr(arc, "opening_words", None)
    if isinstance(raw, (list, tuple)):
        raw = " ".join(str(w) for w in raw)
    if not isinstance(raw, str) or not raw.strip():
        first = arc.segments[0] if arc.segments else None
        raw = (first.transcript_excerpt or "") if first is not None else ""
    return _normalize_text(raw)[:_OPENING_CHARS]


def _has_weak_lead_in(opening: str) -> bool:
    if not opening:
        return False
    tokens = _fold_accents(opening).split()
    head = " ".join(tokens[:_WEAK_LEAD_IN_SCAN_TOKENS])
    if any(p in head for p in _BANNED_OPENER_PHRASES_FOLDED):
        return True
    return bool(tokens) and tokens[0].strip(".,;:!?…") in _BANNED_OPENER_WORDS_FOLDED


def _hook_strength(
    arc: StoryArc,
    per_segment_vision: list[SegmentVision],
    *,
    opening_text: str | None = None,
) -> int:
    """How hard the first 2 seconds grab the viewer. The hook is *verified* on
    the clip's actual opening words (number, charged word, question, weak
    lead-in), not just declared by its length and punctuation."""
    first = arc.segments[0] if arc.segments else None
    if first is None:
        return 40
    base = 40
    dur = max(0.0, first.end - first.start)
    if dur <= 30:  # tight, fast-hitting hook
        base += 8
    ex = first.transcript_excerpt or ""
    if 30 <= len(ex) <= 180:  # meaty but not bloated
        base += 10

    opening = _opening_text(arc, opening_text)
    if _HOOK_DIGIT_RE.search(opening) or _HOOK_MONEY_RE.search(opening):
        base += 12
    if any(w in opening for w in _HOOK_CHARGED_WORDS):
        base += 10
    head = " ".join(opening.split()[:4])
    if "?" in opening or any(w in head for w in _HOOK_QUESTION_WORDS):
        base += 8
    if _has_weak_lead_in(opening):
        base -= WEAK_OPENING_PENALTY

    if per_segment_vision and per_segment_vision[0].vision is not None:
        v = per_segment_vision[0].vision
        if v.person_visible:
            base += 15
        if v.energy >= 70:
            base += 10
        elif v.energy >= 55:
            base += 5
    if arc.suggested_hook and len(arc.suggested_hook) >= 15:
        base += 5
    return max(0, min(100, base))


def _visual_proof(per_segment_vision: list[SegmentVision]) -> int | None:
    scores = [sv.vision.visual_score for sv in per_segment_vision if sv.vision is not None]
    if not scores:
        return None
    # Worst segment dominates — if any segment looks bad, the whole clip suffers
    avg = sum(scores) / len(scores)
    worst = min(scores)
    return round(0.6 * avg + 0.4 * worst)


def _retention(arc: StoryArc) -> int:
    return arc.estimated_retention or 60


def _arc_to_montage_segments(arc: StoryArc) -> list[MontageSegment]:
    return [
        MontageSegment(
            role=s.role if s.role in {"setup", "transition", "payoff", "single"} else "single",  # type: ignore[arg-type]
            start=s.start,
            end=s.end,
            transcript_excerpt=s.transcript_excerpt,
            why=s.why,
        )
        for s in arc.segments
    ]


def score_arc(
    *,
    arc: StoryArc,
    per_segment_vision: list[SegmentVision],
    campaign: dict[str, Any],
    opening_text: str | None = None,
) -> MontageCandidate:
    """Score one arc.

    `opening_text` is the text ACTUALLY spoken in the first
    HOOK_OPENING_WINDOW_SECONDS of the clip, read off the transcript by the
    caller (the runner has `words_in_window`). Passing it moves the hook from
    "what the model declared" to "what the viewer hears"; omitting it keeps the
    previous behaviour, so the simple path and the tests are unaffected.
    """
    visual = _visual_proof(per_segment_vision)
    campaign_fit = _campaign_fit_score(arc, campaign)
    payoff = _payoff_strength(arc, per_segment_vision)
    hook = _hook_strength(arc, per_segment_vision, opening_text=opening_text)
    editing = _editing_continuity_score(arc, per_segment_vision)
    retention = _retention(arc)

    breakdown: dict[str, int] = {
        "payoff_strength": payoff,
        "hook_strength": hook,
        "campaign_fit": campaign_fit,
        "editing_continuity": editing,
        "retention": retention,
    }
    if visual is not None:
        breakdown["visual_proof"] = visual

    # Renormalise if vision is missing
    if visual is None:
        total_weight = sum(w for k, w in ARC_WEIGHTS.items() if k != "visual_proof")
        weighted = sum(
            ARC_WEIGHTS[k] * breakdown[k] for k in ARC_WEIGHTS if k != "visual_proof"
        )
        score_total = round(weighted / total_weight)
    else:
        weighted = sum(ARC_WEIGHTS[k] * breakdown[k] for k in ARC_WEIGHTS)
        score_total = round(weighted)

    # Faceless clips (no visible person in any segment) are almost always weak
    # b-roll for a creator video — knock the score down so face-cam moments win.
    any_person = any(
        sv.vision is not None and sv.vision.person_visible for sv in per_segment_vision
    )
    if per_segment_vision and not any_person:
        score_total = round(score_total * NO_PERSON_PENALTY)

    # The selector's own "this needs outside context" flag was parsed and then
    # ignored. A clip a stranger cannot follow does not work in a feed.
    if not getattr(arc, "self_contained", True):
        score_total -= NOT_SELF_CONTAINED_PENALTY
        log.info(
            "score.not_self_contained",
            title=(arc.title or "")[:80],
            penalty=NOT_SELF_CONTAINED_PENALTY,
        )

    # Montage-v2: multi-segment clips are no longer penalised as a class — the
    # per-joint editing_continuity term already prices in the transition cost.
    score_total = max(0, min(100, score_total))

    # Visual summary (concise)
    visual_summary: str | None = None
    if per_segment_vision:
        bits: list[str] = []
        for sv in per_segment_vision:
            if sv.vision is None:
                continue
            v = sv.vision
            bits.append(
                f"seg{sv.segment_idx + 1}={v.decor}/{v.action}/score{v.visual_score}"
            )
        if bits:
            visual_summary = "; ".join(bits)
        else:
            visual_summary = "vision unavailable"

    transcript_excerpt = " | ".join(
        s.transcript_excerpt for s in arc.segments if s.transcript_excerpt
    )

    return MontageCandidate(
        title=arc.title or None,
        hook=arc.suggested_hook,
        segments=_arc_to_montage_segments(arc),
        rationale=arc.viral_reason or None,
        score_total=max(0, min(100, score_total)),
        score_breakdown=breakdown,
        visual_summary=visual_summary,
        transcript_excerpt=transcript_excerpt or None,
        arc_type=arc.arc_type,
        arc=arc,
    )


# ---------------------------------------------------------------------------
# Diversity
# ---------------------------------------------------------------------------


def _merge_spans(spans: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
    """Footprint on the source timeline, as disjoint windows."""
    merged: list[tuple[float, float]] = []
    for start, end in sorted((s, e) for s, e in spans if e > s):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _merged_spans(candidate: MontageCandidate) -> list[tuple[float, float]]:
    return _merge_spans((s.start, s.end) for s in candidate.segments)


def _spans_total(spans: list[tuple[float, float]]) -> float:
    return sum(end - start for start, end in spans)


def _spans_intersection(
    a: list[tuple[float, float]], b: list[tuple[float, float]]
) -> float:
    total = 0.0
    i = j = 0
    while i < len(a) and j < len(b):
        lo = max(a[i][0], b[j][0])
        hi = min(a[i][1], b[j][1])
        if hi > lo:
            total += hi - lo
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return total


def _temporal_jaccard(
    spans_a: list[tuple[float, float]], spans_b: list[tuple[float, float]]
) -> float:
    """Jaccard on the union of the two clips' source windows. 1.0 = same footage."""
    total_a, total_b = _spans_total(spans_a), _spans_total(spans_b)
    if total_a <= 0 or total_b <= 0:
        return 0.0
    inter = _spans_intersection(spans_a, spans_b)
    union = total_a + total_b - inter
    return inter / union if union > 0 else 0.0


def _redundancy_text(candidate: MontageCandidate) -> str:
    return _normalize_text(
        f"{candidate.title or ''} {candidate.transcript_excerpt or ''}"
    )[:_REDUNDANCY_TEXT_CHARS]


def _text_similarity(ta: str, tb: str) -> float:
    if not ta or not tb:
        return 0.0
    return difflib.SequenceMatcher(None, ta, tb, autojunk=False).ratio()


def _redundancy_of(
    spans_a: list[tuple[float, float]],
    text_a: str,
    spans_b: list[tuple[float, float]],
    text_b: str,
) -> float:
    """0 = unrelated clips, 1 = the customer is being sold the same clip twice.

    Two independent ways of saying the same thing, so we take the worst:
    (a) the clips reuse the same footage, (b) they tell the same story with
    different footage. Either one alone ruins a batch.
    """
    temporal = min(1.0, _temporal_jaccard(spans_a, spans_b) / TEMPORAL_OVERLAP_HARD)
    ratio = _text_similarity(text_a, text_b)
    textual = max(0.0, (ratio - TEXT_SIMILARITY_FLOOR) / (1.0 - TEXT_SIMILARITY_FLOOR))
    return min(1.0, max(temporal, textual))


def _redundancy(a: MontageCandidate, b: MontageCandidate) -> float:
    return _redundancy_of(
        _merged_spans(a), _redundancy_text(a), _merged_spans(b), _redundancy_text(b)
    )


def rank_and_pick(
    candidates: list[MontageCandidate], target_clip_count: int
) -> list[MontageCandidate]:
    """Greedy MMR selection: quality first, but never twice the same clip.

    Each round takes the best remaining candidate after its score has been
    discounted by how redundant it is with what we already picked; anything
    above MMR_DUPLICATE_CUTOFF is dropped instead of shipped. The batch can
    therefore be shorter than target_clip_count — see the constants above.
    """
    limit = max(1, target_clip_count)
    remaining = sorted(
        range(len(candidates)), key=lambda i: candidates[i].score_total, reverse=True
    )
    picked: list[MontageCandidate] = []
    dropped = 0

    while remaining and len(picked) < limit:
        best_pos: int | None = None
        best_effective = -1.0
        for pos, idx in enumerate(remaining):
            cand = candidates[idx]
            redundancy = max((_redundancy(cand, p) for p in picked), default=0.0)
            if redundancy >= MMR_DUPLICATE_CUTOFF:
                continue
            effective = cand.score_total * (1.0 - MMR_LAMBDA * redundancy)
            if best_pos is None or effective > best_effective:
                best_pos, best_effective = pos, effective
        if best_pos is None:
            # Everything left is a rerun of what we already have.
            dropped = len(remaining)
            break
        picked.append(candidates[remaining.pop(best_pos)])

    if dropped:
        log.info(
            "score.diversity_drop",
            dropped=dropped,
            picked=len(picked),
            target=limit,
        )
    return picked


# ---------------------------------------------------------------------------
# Pre-vision selection
# ---------------------------------------------------------------------------
# Deep vision is the expensive step, so its cap must be spent on DISTINCT arcs.
# Ranking on estimated_retention alone bought vision for near-duplicates and let
# the MMR pass throw them away afterwards: the money was already spent, and the
# batch came back short of clips.
ARC_PRESELECT_RETENTION_WEIGHT = 0.55
ARC_PRESELECT_CAMPAIGN_WEIGHT = 0.45


def arc_preselect_score(arc: StoryArc) -> float:
    """Pre-vision ranking: the model's retention guess AND its campaign-fit
    self-report. A high-retention arc that ignores the brief must not outrank a
    calmer one that serves it. 60 = neutral when a field is unreported."""
    retention = arc.estimated_retention or 60
    fit = arc.campaign_fit_llm if arc.campaign_fit_llm is not None else 60
    return (
        ARC_PRESELECT_RETENTION_WEIGHT * retention
        + ARC_PRESELECT_CAMPAIGN_WEIGHT * fit
    )


def _arc_spans(arc: StoryArc) -> list[tuple[float, float]]:
    return _merge_spans((s.start, s.end) for s in arc.segments)


def _arc_redundancy_text(arc: StoryArc) -> str:
    return _normalize_text(
        " ".join([arc.title or "", *[s.transcript_excerpt or "" for s in arc.segments]])
    )[:_REDUNDANCY_TEXT_CHARS]


def preselect_arcs_for_vision(
    arcs: list[StoryArc], limit: int
) -> tuple[list[StoryArc], list[dict[str, Any]]]:
    """Choose which arcs deserve the deep-vision spend: diversity FIRST, cap after.

    Same redundancy measure as rank_and_pick (shared footage or the same story
    retold), applied on the arcs themselves so a duplicate never consumes one of
    the `limit` vision slots. Returns (kept, dropped) — every drop carries its
    reason so the caller can log it against the job.
    """
    cap = max(1, limit)
    order = sorted(range(len(arcs)), key=lambda i: (-arc_preselect_score(arcs[i]), i))
    kept: list[StoryArc] = []
    kept_keys: list[tuple[list[tuple[float, float]], str]] = []
    dropped: list[dict[str, Any]] = []

    for i in order:
        arc = arcs[i]
        spans, text = _arc_spans(arc), _arc_redundancy_text(arc)
        record = {
            "title": (arc.title or "")[:80],
            "preselect_score": round(arc_preselect_score(arc), 1),
        }
        if len(kept) >= cap:
            dropped.append({**record, "reason": "below_vision_cap"})
            continue
        worst, twin = 0.0, None
        for kept_arc, (kept_spans, kept_text) in zip(kept, kept_keys, strict=True):
            redundancy = _redundancy_of(spans, text, kept_spans, kept_text)
            if redundancy > worst:
                worst, twin = redundancy, kept_arc
        if worst >= MMR_DUPLICATE_CUTOFF:
            dropped.append(
                {
                    **record,
                    "reason": "duplicate",
                    "redundancy": round(worst, 3),
                    "duplicate_of": (twin.title or "")[:80] if twin else None,
                }
            )
            continue
        kept.append(arc)
        kept_keys.append((spans, text))

    return kept, dropped
