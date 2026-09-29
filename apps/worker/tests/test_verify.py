import pytest

from app.models import ArcSegmentSpec, Transcript, TranscriptWord
from app.pipeline.verify import verify_segment


def check(source, excerpt):
    tokens = source.split()
    transcript = Transcript(
        source, [TranscriptWord(word, i * 0.25, i * 0.25 + 0.2) for i, word in enumerate(tokens)]
    )
    return verify_segment(transcript, ArcSegmentSpec("single", 0, len(tokens) * 0.25, excerpt))


def test_verifies_subphrase_without_penalty_for_surrounding_window():
    source = (
        "Introduction très longue. « Ce projet rapporte cent euros ! » Puis la conclusion arrive."
    )
    assert check(source, "Ce projet rapporte cent euros.") == (True, 1.0)


@pytest.mark.parametrize(
    "source,excerpt",
    [
        (
            "Le projet ne rapporte pas 100 euros aujourd'hui",
            "Le projet rapporte 100 euros aujourd'hui",
        ),
        ("Le projet rapporte 100 euros aujourd'hui", "Le projet rapporte 1000 euros aujourd'hui"),
        (
            "Le projet rapporte 100 euros aujourd'hui",
            "Le projet ne rapporte pas 100 euros aujourd'hui",
        ),
        (
            "Le projet rapporte cent euros",
            "Le projet rapporte cent euros et j'ai gagné une voiture énorme",
        ),
        ("Le projet rapporte cent euros", ""),
        ("Le projet rapporte cent euros", "Ce passage est totalement inventé"),
    ],
)
def test_rejects_unsupported_quotes_and_changed_claims(source, excerpt):
    assert not check(source, excerpt)[0]


def test_tolerates_minor_name_spelling_but_preserves_claim():
    assert check(
        "Je m'appelle Bernard et je travaille ici depuis plusieurs années",
        "Je m'appelle Bernart et je travaille ici depuis plusieurs années",
    )[0]
