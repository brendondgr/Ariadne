#!/usr/bin/env python3
"""The four verifier gates, individually ablatable — and the invariant that protects every recorded figure.

EXP-2026-08-014 asks what each gate in `_verify_claim` actually cuts. To answer
it the gates have to be switchable, and switching them is exactly the kind of
change that silently moves a number nobody re-checks. So the first test here is
not about ablation at all: it asserts that with every gate on — the default, and
the condition every committed figure was measured under — the verifier's output
is *indistinguishable* from what it was before the switches existed.

The remaining tests pin the ablation semantics: disabling a gate must move its
objection to ``waived`` rather than deleting it, so the ablation counts what a
gate cuts instead of re-deriving it.
"""

from __future__ import annotations

import pytest

from utils.synthesis.config import SynthesisConfig
from utils.synthesis.contracts import Citation, Claim
from utils.synthesis.verifier import _verify_claim

_GATES = ("cited", "resolvable", "grounded", "correlated")


def _cfg(**off: bool) -> SynthesisConfig:
    """A config with the named gates turned off and the rest on."""
    return SynthesisConfig(**{f"gate_{g}": (g not in off) for g in _GATES})


class _Rec:
    """The smallest thing `id_pool` and `_resolve_citation` need."""

    def __init__(self, primary_id: str) -> None:
        self.primary_id = primary_id
        self.provenance = None
        self.join_values = ()
        self.related = []


def _by_source(*ids: str) -> dict[str, list[_Rec]]:
    return {"attack": [_Rec(i) for i in ids]}


# ---------------------------------------------------------------------------
# The invariant. If this breaks, every committed figure is in question.
# ---------------------------------------------------------------------------

def test_default_config_has_every_gate_on() -> None:
    """The default must be all-on, from the dataclass and from an empty env."""
    assert SynthesisConfig().gates_all_on()
    assert SynthesisConfig().disabled_gates() == ()


def test_from_env_defaults_every_gate_on(monkeypatch: pytest.MonkeyPatch) -> None:
    for gate in _GATES:
        monkeypatch.delenv(f"VERIFY_GATE_{gate.upper()}", raising=False)
    assert SynthesisConfig.from_env().gates_all_on()


@pytest.mark.parametrize(
    "claim,records",
    [
        # supported: cited, resolvable, grounded
        (
            Claim(text="t", citations=(Citation("attack", "T1047"),), entity_ids=("T1047",)),
            _by_source("T1047"),
        ),
        # uncited
        (Claim(text="t", entity_ids=("T1047",)), _by_source("T1047")),
        # citation resolves to nothing
        (
            Claim(text="t", citations=(Citation("attack", "T9999"),), entity_ids=("T9999",)),
            _by_source("T1047"),
        ),
        # cited and resolvable, but the asserted entity is not in the records
        (
            Claim(text="t", citations=(Citation("attack", "T1047"),), entity_ids=("T1055",)),
            _by_source("T1047", "T1055"),
        ),
        # correlation with no join backing
        (
            Claim(
                text="t",
                citations=(Citation("attack", "T1047"),),
                entity_ids=("T1047",),
                kind="correlation",
            ),
            _by_source("T1047"),
        ),
    ],
)
def test_all_gates_on_never_waives_and_never_serialises_a_new_key(claim, records) -> None:
    """With gates on, `waived` is empty and `to_dict()` is byte-compatible.

    This is the guarantee that lets EXP-2026-08-014 ship without re-judging the
    recorded answers: the ablation adds a field that is provably absent from the
    serialized form on the default path.
    """
    verdict = _verify_claim(claim, records, {"T1047"}, _cfg())
    assert verdict.waived == ()
    assert "waived" not in verdict.to_dict()


# ---------------------------------------------------------------------------
# Ablation semantics: an objection is moved, never deleted.
# ---------------------------------------------------------------------------

def test_cited_gate_cuts_an_uncited_claim_and_ablating_it_waives_instead() -> None:
    claim = Claim(text="t", entity_ids=("T1047",))
    records = _by_source("T1047")

    on = _verify_claim(claim, records, set(), _cfg())
    assert not on.supported
    assert any("uncited" in r for r in on.reasons)

    off = _verify_claim(claim, records, set(), _cfg(cited=True))
    assert off.supported
    assert any("uncited" in w for w in off.waived), "the objection must survive as waived"
    assert off.reasons == []


def test_resolvable_gate_cuts_a_dangling_citation_and_ablating_it_waives_instead() -> None:
    claim = Claim(
        text="t", citations=(Citation("attack", "T9999"),), entity_ids=("T9999",)
    )
    records = _by_source("T1047")

    on = _verify_claim(claim, records, set(), _cfg())
    assert not on.supported

    off = _verify_claim(claim, records, set(), _cfg(resolvable=True))
    assert off.waived, "the unresolvable-citation objection must be recorded"
    # With `resolvable` ablated the grounding gate is no longer short-circuited,
    # and it correctly fires: nothing resolved, so nothing grounds T9999.
    assert not off.supported
    assert any("not grounded" in r for r in off.reasons)


def test_grounded_gate_cuts_an_ungrounded_entity_and_ablating_it_waives_instead() -> None:
    claim = Claim(
        text="t", citations=(Citation("attack", "T1047"),), entity_ids=("T1055",)
    )
    records = _by_source("T1047", "T1055")

    on = _verify_claim(claim, records, set(), _cfg())
    assert not on.supported
    assert any("not grounded" in r for r in on.reasons)

    off = _verify_claim(claim, records, set(), _cfg(grounded=True))
    assert off.supported
    assert any("not grounded" in w for w in off.waived)


def test_correlated_gate_cuts_an_unbacked_correlation_and_ablating_it_waives_instead() -> None:
    claim = Claim(
        text="t",
        citations=(Citation("attack", "T1047"),),
        entity_ids=("T1047",),
        kind="correlation",
    )
    records = _by_source("T1047")

    on = _verify_claim(claim, records, set(), _cfg())
    assert not on.supported
    assert any("join index" in r for r in on.reasons)

    off = _verify_claim(claim, records, set(), _cfg(correlated=True))
    assert off.supported
    assert any("join index" in w for w in off.waived)

    # And it must not fire at all when the join index does back the correlation.
    backed = _verify_claim(claim, records, {"T1047"}, _cfg())
    assert backed.supported and backed.waived == ()


def test_correlated_gate_is_inert_on_a_fact_claim() -> None:
    """Ablating `correlated` must not change a non-correlation claim."""
    claim = Claim(
        text="t", citations=(Citation("attack", "T1047"),), entity_ids=("T1047",)
    )
    records = _by_source("T1047")
    assert _verify_claim(claim, records, set(), _cfg()).to_dict() == _verify_claim(
        claim, records, set(), _cfg(correlated=True)
    ).to_dict()


def test_disabled_gates_are_reported_for_the_run_manifest() -> None:
    assert _cfg(grounded=True).disabled_gates() == ("grounded",)
    assert set(_cfg(cited=True, correlated=True).disabled_gates()) == {"cited", "correlated"}
    assert not _cfg(grounded=True).gates_all_on()
