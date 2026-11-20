"""Phase E (EXP-2026-11-021): a small seeded Cypher/Gremlin differential on ATT&CK + CAPEC.

The full run is ``python -m utils.specialists.algebra.differential --seed 20261120
--random 3000 --out DIR``. This test draws a seeded sample of the same generator
(card instances and random compositions over the combined card) and requires zero
disagreements and zero one-sided errors, apart from the
instances ``known_issue`` marks (reported to the operator, never tolerated silently). It skips when the verification pair
(bolt 5480, ws 6480) is not reachable.
"""

from __future__ import annotations

import random

import pytest

from utils.specialists.algebra.differential import (Engines, Sampler, card_instances, combined_card, random_instance,
                                                    run_instance, stores_up)

pytestmark = pytest.mark.skipif(not stores_up(), reason="verification stores (bolt 5480, ws 6480) unreachable")
SEED = 20261120
N_CARD, N_RANDOM = 150, 150


def test_small_seeded_differential_agrees():
    rng = random.Random(SEED)
    engines = Engines()
    try:
        card = combined_card()
        s = Sampler(engines, card, rng)
        insts = card_instances(card, s)
        insts = random.Random(SEED).sample(insts, min(N_CARD, len(insts)))
        i = 0
        while sum(1 for x in insts if x.family == "random") < N_RANDOM:
            i += 1
            inst = random_instance(card, s, i)
            if inst is not None:
                insts.append(inst)
        rows = [run_instance(engines, inst, card) for inst in insts]
    finally:
        engines.close()
    assert len(rows) == N_CARD + N_RANDOM
    # Instances blocked by a known, reported store/semantics issue (``known_issue``:
    # list encoding, walk edge reuse) are counted apart; every other must agree.
    bad = [(r["iid"], r["operator"], r.get("diffs") or r.get("errors")) for r in rows
           if r["status"] not in ("agree", "both_refused") and not r.get("known")]
    assert not bad, bad[:5]
    assert sum(r["status"] == "agree" for r in rows) >= 0.9 * len(rows)
