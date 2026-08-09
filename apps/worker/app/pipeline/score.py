from __future__ import annotations

import difflib
import re
import unicodedata
from collections.abc import Iterable
from typing import Any

import structlog

from ..models import (
    AudienceHeatmap,
    MontageCandidate,
    MontageSegment,
    SegmentVision,
    StoryArc,
    VisionResult,
)

log = structlog.get_logger()

# Montage-v2 weights, as they stood before the audience term existed. Kept under
# their own name because they are the reference the renormalisation below has to
# reproduce exactly whenever a video has no re-watch curve — see ARC_WEIGHTS.
# Multi-segment clips are first-class now, so the mix leans on campaign fit and
# payoff strength alongside watchability and a first-2-seconds hook. The LLM's
# self-reported retention stays discounted. Sums to 1.0.
#
# campaign_fit went 0.12 -> 0.20 when it stopped being a flat 60. At 0.12 it
# could not move a ranking even when it was right (a 30-point fit gap was worth
# 3.6 points of final score, less than the rounding noise on visual_proof); the
# product we sell is "clips chosen FOR your campaign", so the one term that
# measures that has to be able to reorder the batch. At 0.20 the same gap is
# worth 6 points — enough to flip two clips of comparable craft, not enough to
# ship an ugly one. visual_proof stays first because a clip that looks bad is
# unusable whatever it says. The 0.08 comes out of the three terms that were
# double-counting watchability (hook, payoff, editing_continuity) and out of
# nothing else; retention keeps its discount for being an LLM self-report.
_PRE_AUDIENCE_ARC_WEIGHTS = {
    "visual_proof": 0.26,
    "campaign_fit": 0.20,
    "hook_strength": 0.18,
    "payoff_strength": 0.16,
    "editing_continuity": 0.10,
    "retention": 0.10,
}

# How much of the score YouTube's real re-watch curve is allowed to move.
#
# Every other term above is somebody's opinion — a model's guess (retention,
# payoff), a lexicon we wrote (campaign_fit), a heuristic (hook). This one is
# measured behaviour: viewers went back and watched that exact second again.
# That is why it gets a share comparable to campaign_fit rather than the token
# weight of a tie-breaker.
#
# 0.12 and not more, because the term is loud by construction: it is a
# percentile, so within one video it spreads across the full 0..100 range where
# campaign_fit realistically spans ~30 points. At 0.12 a peak arc beats a
# trough arc by ~10 points of final score — enough to reorder two clips of
# comparable craft, never enough to ship an ugly or off-brief one just because
# people re-watched that bit. It also stays below visual_proof: a moment the
# audience loved is worthless if the frame is unusable.
AUDIENCE_WEIGHT = 0.12

# The 0.12 is taken PRO RATA from every existing term rather than carved out of
# one of them. That is not a cosmetic choice: when a video has no curve — which
# is the common case, not the edge case — score_arc drops the term and
# renormalises, and proportional shaving makes those renormalised weights come
# back to _PRE_AUDIENCE_ARC_WEIGHTS exactly. So a job without a heatmap keeps
# today's scores to the point, and shipping this cannot re-rank a single
# existing job. Sums to 1.0.
ARC_WEIGHTS = {
    **{
        key: round(weight * (1.0 - AUDIENCE_WEIGHT), 6)
        for key, weight in _PRE_AUDIENCE_ARC_WEIGHTS.items()
    },
    "audience": AUDIENCE_WEIGHT,
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
        # goal boilerplate: what the clip must DO to the viewer, never what it
        # must talk about. Left in, they became dead units the clip could never
        # cover ("inciter" is not a word anybody says on camera) and capped the
        # achievable fit for every arc alike.
        "inciter", "incite", "pousser", "pousse", "amener", "convaincre",
        "persuader", "generer", "générer", "augmenter", "donner", "envie",
        "objectif", "objectifs", "afin",
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

# ---------------------------------------------------------------------------
# Campaign lexicon — the brief and the video do not speak the same language
# ---------------------------------------------------------------------------
# Measured on the production brief: comparing the brief's WORDS to the clip's
# words returned the neutral baseline on 4 arcs out of 5, so campaign_fit came
# out at 74/75/75/75/80 while the selection model was reporting 88-100. The
# typos were never the cause (fuzzy matching already absorbs "buinesse" ~
# "business"): the cause is that the brief says "business, formation, jeunes"
# and the clips say "e-commerce, boutique, dropshipping, coaching". Comparing
# words cannot bridge that, however tolerant the comparison is.
#
# So both sides are projected onto a small hard-coded map of French
# business/formation/e-commerce concepts before being compared. Said plainly:
# this is a lexicon, not semantics. There is no embedding and no second model
# call — an arc must not cost another LLM round-trip. It covers the vertical we
# sell into and nothing else; outside it no concept lights up, the brief's own
# words are still matched literally, and the score leans back on the selection
# model's self-report. That fallback is the design, not a silent failure.

# A stem of 4+ characters matches any word starting with it that adds at most
# _STEM_MAX_SUFFIX letters — enough for French inflection ("lanc" -> lancer,
# lancé, lançant) and short enough that a stem cannot reach an unrelated family
# ("lanc" never gets to "lancinante"). It is a prefix rule, not a lemmatiser:
# "vendre" also matches "vendredi", and that is the price we pay for having no
# NLP dependency. Stems shorter than that are matched as whole words only, so
# "pub" cannot fire on "public". Everything is compared accent-folded — whisper
# writes "bénéfice", the table below stays ASCII.
_MIN_STEM_LEN = 4
_STEM_MAX_SUFFIX = 3

_CONCEPT_STEMS: dict[str, tuple[str, ...]] = {
    # Selling something: the activity itself.
    "commerce": (
        "business", "busines", "buisness", "entrepr", "commerc", "boutique",
        "ecommerce", "dropship", "shopify", "vente", "vendr", "vendu",
        "vends", "client", "clientele", "produit", "marque", "magasin",
        "commande", "achet", "panier", "fournisseur", "livraison", "niche",
    ),
    # What a creator sells to their audience — the thing a "buy my formation"
    # brief is actually about.
    "formation": (
        "formation", "coach", "accompagn", "mentor", "apprend", "apprenti",
        "enseign", "cours", "methode", "tuto", "connaissance", "competence",
        "savoir", "conseil", "astuce", "strategi", "technique", "programme",
        "masterclass", "atelier",
    ),
    # Money on the table.
    "argent": (
        "euro", "dollar", "argent", "benefic", "marge", "profit", "revenu",
        "chiffre", "gagn", "cash", "budget", "rentab", "invest", "monetis",
        "salaire", "prix", "coute", "depens", "million", "millier", "milliard",
        "balle", "riche", "fortune", "payer",
    ),
    # Proof that it worked.
    "resultat": (
        "resultat", "preuve", "prouv", "reussi", "reussit", "succes", "record",
        "performan", "croissance", "scale", "cartonn", "explos", "challenge",
        "conversion", "statistiq", "progress", "atteint", "multipli",
    ),
    # Starting from nothing, and the young audience briefs keep asking for.
    "debutant": (
        "jeune", "debut", "commenc", "demarr", "lanc", "lancement", "novice",
        "etudiant", "zero", "premier", "premiere", "amateur",
    ),
    # The lifestyle a brief sells alongside the method.
    "luxe": (
        "luxe", "luxu", "voiture", "villa", "voyage", "ferrari", "porsche",
        "rolex", "piscine", "penthouse", "yacht", "palace", "premium",
    ),
    # Where the customers come from.
    "trafic": (
        "publicit", "tiktok", "instagram", "facebook", "youtube", "google",
        "algorithm", "audience", "trafic", "visite", "abonne", "ciblag",
        "campagne", "annonce", "influenc", "pub", "ads", "seo",
    ),
    # The head game every formation brief leans on.
    "mindset": (
        "mental", "mindset", "discipline", "motiv", "ambit", "sacrifi",
        "risque", "echec", "abandon", "persever", "liberte", "independan",
        "rigueur", "habitude", "confiance",
    ),
}

# A brief word the lexicon does not know is still honoured, but at half weight:
# a literal match is the weakest evidence we have, and half of a dirty brief is
# noise ("quete", "train" from "train de vie").
LITERAL_UNIT_WEIGHT = 0.5

# What the goal asks the clip to DO. Triggers are read in the goal only.
# "formation" is deliberately absent from "teach": in "acheter sa formation" it
# names the product, not the intent.
_GOAL_INTENTS: dict[str, tuple[str, ...]] = {
    "sell": (
        "achet", "vendr", "vente", "convert", "inscri", "souscri", "command",
        "client", "prospect", "reserv", "abonnement", "payant", "acquer",
    ),
    "teach": (
        "apprend", "enseign", "eduqu", "expliqu", "pedagog", "tuto",
        "vulgaris", "comprend", "maitris", "transmet",
    ),
    "authority": (
        "notoriete", "credibil", "autorite", "reputation", "visibilit",
        "branding", "expert", "reference",
    ),
    "audience": (
        "abonne", "communaut", "audience", "follower", "engagement", "viral",
        "grandir",
    ),
}

# A number, a currency or an order of magnitude: the cheapest proof a viewer can
# check in one second.
_FIGURE_RE = re.compile(
    r"\d|[€$£%]|\b(?:euros?|dollars?|pourcents?|mille|milliers?|millions?|"
    r"milliards?|centaines?|dizaines?)\b"
)

# Evidence axes: what has to be visible IN THE CLIP for an intent to be served.
# Concept-backed axes reuse the table above; the rest carry their own stems.
_AXIS_CONCEPTS: dict[str, tuple[str, ...]] = {
    "result": ("resultat", "argent"),   # something worked, or it made money
    "offer": ("formation",),            # the thing the goal wants bought is named
    "method": ("formation", "trafic"),  # something actionable is handed over
    "emotion": ("mindset",),
}
_AXIS_STEMS: dict[str, tuple[str, ...]] = {
    # A track record or a before/after — what makes the claim believable.
    "track_record": (
        "million", "milliard", "experience", "parcours", "clientele",
        "temoignage", "eleve", "carriere", "annee", "transform", "desormais",
        "autrefois", "epoque", "grace", "aujourd",
    ),
}
_INTENT_AXES: dict[str, tuple[str, ...]] = {
    "sell": ("figure", "result", "offer", "track_record"),
    "teach": ("method", "figure", "result"),
    "authority": ("track_record", "result", "figure"),
    "audience": ("emotion", "figure", "result"),
}

# Final mix. Both halves neutral (nothing known about the brief) lands on 60,
# the baseline the previous keyword score returned — so an empty or off-vertical
# campaign scores exactly as it used to. The goal weighs twice the subject: a
# brief's audience/niche say which world the clip lives in, its goal says what
# the clip must make the viewer do, and that is what the customer is buying.
FIT_BASE = 30
FIT_TOPICAL_SPAN = 20
FIT_INTENT_SPAN = 40
_NEUTRAL_HALF = 0.5


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
    """Everything the arc carries, the model's own rationale included. Used by
    the avoid scan, which must cast the widest possible net."""
    return " ".join(
        [
            arc.title or "",
            arc.viral_reason or "",
            arc.suggested_hook or "",
            *[s.transcript_excerpt or "" for s in arc.segments],
        ]
    ).lower()


def _spoken_text(arc: StoryArc) -> str:
    """What the clip actually IS: its title, its hook, and the words on the tape.

    viral_reason is deliberately left out. It is the selection model's
    commentary about the clip ("directly supports the goal of selling his
    business formation"), and the other half of the campaign_fit blend is
    already that model's opinion — reading it here too would dress a self-report
    up as independent evidence and guarantee agreement with itself.
    """
    return " ".join(
        [
            arc.title or "",
            arc.suggested_hook or "",
            *[s.transcript_excerpt or "" for s in arc.segments],
        ]
    ).lower()


def _folded_words(text: str) -> set[str]:
    return {_fold_accents(w) for w in _TOKEN_RE.findall(text.lower())}


def _stem_index(words: Iterable[str]) -> set[str]:
    """Every prefix a stem could plausibly be for these words: the word itself
    down to _STEM_MAX_SUFFIX letters shorter. Turns stem lookup into set
    membership instead of a startswith() scan over the whole table.

    French plurals get their own pass, otherwise the suffix budget is spent on
    the -s and the stem falls short: "coachings" would never reach "coach".
    """
    out: set[str] = set()
    for word in words:
        forms = [word]
        if len(word) > _MIN_STEM_LEN and word.endswith(("s", "x")):
            forms.append(word[:-1])
        for form in forms:
            floor = max(_MIN_STEM_LEN, len(form) - _STEM_MAX_SUFFIX)
            for size in range(floor, len(form) + 1):
                out.add(form[:size])
    return out


def _matches_stem(stem: str, words: set[str], index: set[str]) -> bool:
    return stem in index if len(stem) >= _MIN_STEM_LEN else stem in words


def _concepts_of(words: set[str]) -> set[str]:
    """Concepts a piece of text activates.

    No fuzzy pass on this side: transcripts are clean text, and a
    SequenceMatcher call per (word x stem) pair would cost hundreds of
    thousands of comparisons per arc for nothing.
    """
    index = _stem_index(words)
    return {
        concept
        for concept, stems in _CONCEPT_STEMS.items()
        if any(_matches_stem(stem, words, index) for stem in stems)
    }


def _concept_of_brief_word(word: str) -> str | None:
    """Which concept a single brief word belongs to, or None.

    The brief is hand-typed and filthy, so this side keeps the fuzzy pass —
    that is how "buinesse" reaches "business" and, through it, the whole
    e-commerce vocabulary the clips actually use.
    """
    index = _stem_index([word])
    for concept, stems in _CONCEPT_STEMS.items():
        for stem in stems:
            if _matches_stem(stem, {word}, index):
                return concept
            if len(stem) >= _MIN_STEM_LEN and _fuzzy_contains(stem, {word}):
                return concept
    return None


def _campaign_lexicon(campaign: dict[str, Any]) -> tuple[frozenset[str], frozenset[str]]:
    """Expand goal + audience + niche into what we will look for in the clips.

    Returns (concepts, literals). Every significant brief word is either
    recognised as one of the hard-coded concepts — and then the whole concept,
    i.e. all of its surface forms, is what a clip has to hit — or kept as a
    literal word, still fuzzy-matched, so a brief outside our vertical is
    degraded rather than ignored.
    """
    concepts: set[str] = set()
    literals: set[str] = set()
    for field in ("goal", "audience", "niche"):
        for word in _significant_words(str(campaign.get(field) or "")):
            folded = _fold_accents(word)
            concept = _concept_of_brief_word(folded)
            if concept is not None:
                concepts.add(concept)
            else:
                literals.add(folded)
    return frozenset(concepts), frozenset(literals)


def _topical_fit(
    clip_words: set[str], clip_concepts: set[str], campaign: dict[str, Any]
) -> float | None:
    """Share of what the brief is ABOUT that the clip also covers, 0..1.

    A recall, not a bonus stack: the old score only ever went up, so every arc
    drifted back to the baseline. None when the brief says nothing usable.
    """
    concepts, literals = _campaign_lexicon(campaign)
    total = len(concepts) + LITERAL_UNIT_WEIGHT * len(literals)
    if total <= 0:
        return None
    covered = float(len(concepts & clip_concepts))
    covered += LITERAL_UNIT_WEIGHT * sum(
        1 for word in literals if _fuzzy_contains(word, clip_words)
    )
    return min(1.0, covered / total)


def _intent_fit(
    spoken: str, clip_words: set[str], clip_concepts: set[str], intents: set[str]
) -> float | None:
    """Share of the goal's evidence axes the clip satisfies, 0..1.

    This is the half that separates "talks about business" from "makes someone
    buy the formation": a proof, a figure, the offer itself, a track record.
    None when the goal expresses no intent we know how to check.
    """
    axes = sorted({axis for intent in intents for axis in _INTENT_AXES[intent]})
    if not axes:
        return None
    index = _stem_index(clip_words)
    hits = 0
    for axis in axes:
        if axis == "figure":
            found = bool(_FIGURE_RE.search(spoken))
        else:
            found = any(c in clip_concepts for c in _AXIS_CONCEPTS.get(axis, ())) or any(
                _matches_stem(stem, clip_words, index)
                for stem in _AXIS_STEMS.get(axis, ())
            )
        hits += int(found)
    return hits / len(axes)


def _goal_intents(campaign: dict[str, Any]) -> set[str]:
    words = {
        _fold_accents(w) for w in _significant_words(str(campaign.get("goal") or ""))
    }
    if not words:
        return set()
    index = _stem_index(words)
    return {
        intent
        for intent, triggers in _GOAL_INTENTS.items()
        if any(_matches_stem(trigger, words, index) for trigger in triggers)
    }


def _avoid_penalty(arc: StoryArc, campaign: dict[str, Any]) -> int:
    """Sanitised avoid-list penalty. Scanned on the widest text and with the
    stricter fuzzy threshold: a false positive here silently kills a good clip,
    so a messy brief must cost nothing."""
    words = set(_TOKEN_RE.findall(_clip_text(arc)))
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
    return penalty


def _brief_fit_score(arc: StoryArc, campaign: dict[str, Any]) -> int:
    """How well the clip serves this brief, measured on concepts and evidence.

    Two questions, asked separately because they fail separately:
      * topical — does the clip live in the world the brief describes?
      * intent  — does it do what the goal asks (proof, figure, offer, track
        record)? A clip can be perfectly on-topic and still sell nothing.
    Either half falls back to neutral when the brief does not answer it, so an
    empty campaign still scores 60 exactly as before. The avoid list is
    subtracted afterwards, unchanged.
    """
    spoken = _spoken_text(arc)
    clip_words = _folded_words(spoken)
    clip_concepts = _concepts_of(clip_words)

    topical = _topical_fit(clip_words, clip_concepts, campaign)
    intent = _intent_fit(spoken, clip_words, clip_concepts, _goal_intents(campaign))

    fit = round(
        FIT_BASE
        + FIT_TOPICAL_SPAN * (_NEUTRAL_HALF if topical is None else topical)
        + FIT_INTENT_SPAN * (_NEUTRAL_HALF if intent is None else intent)
    )
    return max(0, min(100, fit - _avoid_penalty(arc, campaign)))


def _campaign_fit_score(arc: StoryArc, campaign: dict[str, Any]) -> int:
    """Blend the LLM's campaign-fit self-report with the measured brief fit.

    Kept at half and half. The self-report is informed (the model read the
    brief) but compressed — on the production run it returned 90-100 for every
    single arc, which carries almost no ranking signal. The measured half is
    blunter but actually spreads, so together they rank; alone, neither does.
    Falls back to a neutral 60 for the LLM half when it did not report a value.
    """
    brief_fit = _brief_fit_score(arc, campaign)
    llm = arc.campaign_fit_llm if arc.campaign_fit_llm is not None else 60
    return max(0, min(100, round(0.5 * llm + 0.5 * brief_fit)))


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


def _audience_score(arc: StoryArc, heatmap: AudienceHeatmap | None) -> int | None:
    """How hard THIS video's own audience re-watched the footage of this arc, 0..100.

    The arc's mean intensity is duration-weighted across its segments (a 3 s
    setup must not outweigh a 25 s payoff), then ranked against the video's own
    100 buckets. Percentile and not "value x 100" for two reasons: the curve is
    normalised per video so the raw level says nothing, and the ranking is what
    we actually want — "re-watched more than the rest of this video".

    Known artefact, kept on purpose: the first seconds of almost any YouTube
    video sit high on the curve (people restart it), so arcs opening at t=0 get
    a real edge here. That is genuine audience behaviour and the term is only
    worth AUDIENCE_WEIGHT, so we take it as it comes rather than "correcting"
    measured data with a hand-made curve of our own.

    None when there is no curve, or when nothing about the arc overlaps it —
    the caller then removes the term entirely instead of feeding it a guess.
    """
    if heatmap is None or not heatmap.points or not arc.segments:
        return None
    weighted = 0.0
    covered = 0.0
    for segment in arc.segments:
        intensity = heatmap.intensity_between(segment.start, segment.end)
        if intensity is None:
            continue
        duration = max(segment.end - segment.start, 0.0) or 1.0
        weighted += intensity * duration
        covered += duration
    if covered <= 0:
        return None
    return round(heatmap.percentile_of(weighted / covered))


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
    audience_heatmap: AudienceHeatmap | None = None,
) -> MontageCandidate:
    """Score one arc.

    `opening_text` is the text ACTUALLY spoken in the first
    HOOK_OPENING_WINDOW_SECONDS of the clip, read off the transcript by the
    caller (the runner has `words_in_window`). Passing it moves the hook from
    "what the model declared" to "what the viewer hears"; omitting it keeps the
    previous behaviour, so the simple path and the tests are unaffected.

    `audience_heatmap` is YouTube's re-watch curve for the source, when it
    published one. Absent (the common case), the audience term is dropped and
    the remaining weights renormalise back to what they were before the term
    existed — see ARC_WEIGHTS.
    """
    visual = _visual_proof(per_segment_vision)
    campaign_fit = _campaign_fit_score(arc, campaign)
    payoff = _payoff_strength(arc, per_segment_vision)
    hook = _hook_strength(arc, per_segment_vision, opening_text=opening_text)
    editing = _editing_continuity_score(arc, per_segment_vision)
    retention = _retention(arc)
    audience = _audience_score(arc, audience_heatmap)

    breakdown: dict[str, int] = {
        "payoff_strength": payoff,
        "hook_strength": hook,
        "campaign_fit": campaign_fit,
        "editing_continuity": editing,
        "retention": retention,
    }
    if visual is not None:
        breakdown["visual_proof"] = visual
    if audience is not None:
        breakdown["audience"] = audience

    # Renormalise over the terms we could actually measure. A missing term is
    # removed, never replaced by a neutral value: a fabricated 50 would drag
    # every real score towards the middle and flatten the ranking.
    scored = [k for k in ARC_WEIGHTS if k in breakdown]
    total_weight = sum(ARC_WEIGHTS[k] for k in scored)
    weighted = sum(ARC_WEIGHTS[k] * breakdown[k] for k in scored)
    score_total = round(weighted / total_weight) if total_weight > 0 else 0

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
