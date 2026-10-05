"""Bidder name normalisation. The same contractor shows up as "ABC Constr., Inc." and
"A.B.C. Construction Inc" across tabs; name_key() collapses those, and anything fuzzier
goes to a human (`bidders review`) — never an automatic merge."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

LEGAL_SUFFIXES = {
    "llc", "l l c", "inc", "incorporated", "corp", "corporation", "co", "company", "ltd", "limited",
    "lp", "llp", "pllc", "pa", "pc", "plc", "of florida", "of fl",
}
FUZZY_THRESHOLD = 0.88


def name_key(raw: str) -> str:
    """Lower-case key: '&'->'and', drop punctuation, legal suffixes and any 'dba' trade name."""
    s = (raw or "").lower().strip()
    s = re.split(r"\b(?:d/b/a|dba|d\.b\.a\.?|a/k/a|aka)\b", s)[0]
    s = s.replace("&", " and ")
    s = re.sub(r"(?<=\b[a-z])\.(?=[a-z]\b)", "", s)  # A.B.C. -> ABC
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    changed = True
    while changed and s:
        changed = False
        for suffix in sorted(LEGAL_SUFFIXES, key=len, reverse=True):
            if s.endswith(" " + suffix):
                s = s[: -len(suffix) - 1].strip()
                changed = True
    s = re.sub(r"^the ", "", s)
    # "a b c construction" -> "abc construction"
    s = re.sub(r"\b(?:[a-z] )+[a-z]\b", lambda m: m.group(0).replace(" ", ""), s)
    return s


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, name_key(a), name_key(b)).ratio()


def near_matches(raw: str, known: dict[str, str], threshold: float = FUZZY_THRESHOLD) -> list[tuple[str, float]]:
    """known maps name_key -> canonical name. Returns canonical names that look like `raw` but differ."""
    key = name_key(raw)
    out = []
    for k, canonical in known.items():
        if k == key:
            continue
        score = SequenceMatcher(None, key, k).ratio()
        if score >= threshold:
            out.append((canonical, round(score, 3)))
    return sorted(out, key=lambda t: -t[1])
