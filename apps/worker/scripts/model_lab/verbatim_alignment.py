"""Compare lexical atoms without changing the authoritative ASR word clock."""

import copy
import difflib
import re

ELISION = re.compile(r"^(j|l|d|c|s|n|m|t|qu|jusqu|puisqu|lorsqu)(['\u2019].+)$", re.I)


def atoms(token):
    match = ELISION.match(token)
    return list(match.groups()) if match else [token]


def align_verbatim(transcript, ids, text, normalize):
    result = copy.deepcopy(transcript)
    tokens = []
    for token in re.findall(r"\S+", text):
        if not normalize(token) and tokens:
            tokens[-1] += token
        else:
            tokens.append(token)
    original = [(wid, atom) for wid in ids for atom in atoms(transcript.words[wid].word)]
    native = [atom for token in tokens for atom in atoms(token)]
    matcher = difflib.SequenceMatcher(
        None,
        [normalize(atom) for _, atom in original],
        [normalize(atom) for atom in native],
        autojunk=False,
    )
    mapped = {}
    unresolved = []
    for tag, a, b, c, d in matcher.get_opcodes():
        if tag == "equal" or (tag == "replace" and b - a == d - c and b - a <= 8):
            for left, right in zip(range(a, b), range(c, d), strict=True):
                mapped[left] = native[right]
        else:
            word_ids = list(dict.fromkeys(wid for wid, _ in original[a:b]))
            unresolved.append(
                {
                    "operation": tag,
                    "word_ids": word_ids,
                    "original": [transcript.words[wid].word for wid in word_ids],
                    "second_asr": native[c:d],
                }
            )
    positions = {}
    for position, (wid, _) in enumerate(original):
        positions.setdefault(wid, []).append(position)
    changes = []
    for wid, indexes in positions.items():
        if all(index in mapped for index in indexes):
            new_word = "".join(mapped[index] for index in indexes)
            if new_word != result.words[wid].word:
                changes.append(
                    {"word_id": wid, "before": result.words[wid].word, "after": new_word}
                )
                result.words[wid].word = new_word
    return result, {
        "ratio": matcher.ratio(),
        "changes": changes,
        "unresolved": unresolved,
        "clock_changed": False,
        "comparison": "French elision lexical atoms",
    }
