#!/usr/bin/env python3
"""Identifier scanning + canonicalisation for correctness scoring.

The deterministic synthesis composer states related ids in the *prose* of a
claim ("Found 4 item(s) related to T1047 (e.g. M1038, M1040, M1018)") rather
than only in a claim's structured ``entity_ids``. To grade an answer's
correctness against the golden expected id set we therefore scan every id-shaped
token the answer actually names. The id shapes mirror
``utils.specialists.resolve`` (ATT&CK) and CAPEC/CWE forms.
"""

from __future__ import annotations

import re

# Longer / letter-prefixed forms first so "TA0006" is not read as "T0006" and
# "CAPEC-98" is not read as campaign "C..". Alternation is first-match per
# position in Python's ``re``, so ordering disambiguates.
_ID_RE = re.compile(
    r"\b("
    r"CAPEC[-\s]?\d+"
    r"|CWE[-\s]?\d+"
    r"|TA\d{4}"
    r"|DET\d{4}"
    r"|DC\d{4}"
    r"|DS\d{4}"
    r"|T\d{4}(?:\.\d{3})?"
    r"|M\d{4}"
    r"|G\d{4}"
    r"|S\d{4}"
    r"|C\d{4}"
    r")\b",
    re.IGNORECASE,
)


def canonical(token: str) -> str:
    """Normalise one raw id token to its canonical form (upper-case, dashed)."""
    token = token.strip().upper()
    # CAPEC 98 / CAPEC98 -> CAPEC-98 ; CWE 200 -> CWE-200
    token = re.sub(r"^(CAPEC|CWE)[-\s]?(\d+)$", r"\1-\2", token)
    return token


def scan_ids(text: str) -> list[str]:
    """Return ordered-unique canonical ids named in ``text`` (empty for falsy)."""
    if not text:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for match in _ID_RE.finditer(text):
        cid = canonical(match.group(1))
        if cid not in seen:
            seen.add(cid)
            out.append(cid)
    return out


def canonical_set(ids) -> set[str]:
    """Canonicalise an iterable of ids into a set."""
    return {canonical(str(i)) for i in ids if i}
