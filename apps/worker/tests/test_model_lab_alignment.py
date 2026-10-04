"""French tokenization differences must not masquerade as ASR disagreement."""

import importlib.util
import re
from pathlib import Path
from types import SimpleNamespace

SCRIPT = Path(__file__).parents[1] / "scripts/model_lab/verbatim_alignment.py"
SPEC = importlib.util.spec_from_file_location("lab_alignment", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def transcript(tokens):
    return SimpleNamespace(
        words=[
            SimpleNamespace(word=word, start=i * 0.1, end=(i + 1) * 0.1)
            for i, word in enumerate(tokens)
        ]
    )


def align(tokens, native):
    t = transcript(tokens)
    result, report = MODULE.align_verbatim(
        t,
        list(range(len(tokens))),
        native,
        lambda word: re.sub(r"[^\w]", "", word.casefold()),
    )
    assert [(w.start, w.end) for w in result.words] == [(w.start, w.end) for w in t.words]
    assert len(result.words) == len(t.words)
    return result, report


def test_mixed_split_and_merged_french_elisions_keep_word_ids_and_clocks():
    result, report = align(
        ["J", "'ai", "créé", "Blast", "parce", "qu\u2019il", "n", "'est", "pas", "accessible."],
        "J'ai créé Blast parce qu'il n'est pas accessible.",
    )
    assert report["ratio"] == 1
    assert report["unresolved"] == []
    assert result.words[5].word == "qu'il"
    assert result.words[8].word == "pas"


def test_missing_negation_is_unresolved_and_kept_in_original_clock():
    result, report = align(["Ce", "n'est", "pas", "rentable."], "Ce n'est rentable.")
    assert result.words[2].word == "pas"
    assert any(2 in entry["word_ids"] for entry in report["unresolved"])


def test_translation_of_english_speech_is_not_treated_as_french_tokenization():
    _, report = align(
        ["Cette", "application", "vous", "aide", "à", "apprendre", "des", "langues."],
        "This application helps you learn languages through videos.",
    )
    assert report["ratio"] < 0.84
