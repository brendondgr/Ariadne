#!/usr/bin/env python3
"""Tests for identity gold and the identity bank sampler.

The load-bearing test in this file is
:meth:`TestGoldIsIndependent.test_spec_derived_gold_agrees_with_a_direct_graph_read`.
Gold is computed from the blueprint and answers come from the loaded store; if
those two ever disagree, either the build or the load is wrong, and the whole
experiment rests on being able to tell. It runs against the live store when one
is up and skips otherwise.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from utils.kg_builder.catalog import apply_inferred, catalog_dir, read_catalog
from utils.kg_builder.catalog.declared import DECLARED
from utils.kg_builder.synthetic import generate
from utils.kg_builder.synthetic.spec import TenantSpec
from utils.specialists.evalset.identity_bank import (
    AUTHOR_SYSTEM,
    author_all,
    author_prompt,
    compile_bank,
    draw,
)
from utils.specialists.evalset.identity_gold import (
    DESCRIBE,
    FACET_IN,
    FACET_OUT,
    HOMO_IN,
    HOMO_OUT,
    MULTIHOP,
    UNANSWERABLE,
    facet_gold,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
SPEC_PATH = REPO_ROOT / "data/identity/graphs/identity/canonical/spec.json"


@pytest.fixture(scope="module")
def spec() -> TenantSpec:
    if SPEC_PATH.is_file():
        return TenantSpec.read(SPEC_PATH)
    if not (catalog_dir() / "node_attributes.csv").is_file():
        pytest.skip("neither a built tenant nor the ReliaQuest delivery is present")
    catalog = apply_inferred(read_catalog(name="identity"))
    _nodes, _edges, built = generate(catalog, seed=20260821)
    return built


class TestGoldShape:
    def test_the_draw_is_deterministic(self, spec) -> None:
        a, _ = draw(spec, seed=7)
        b, _ = draw(spec, seed=7)
        assert [e.to_dict() for e in a] == [e.to_dict() for e in b]

    def test_a_different_seed_draws_different_anchors(self, spec) -> None:
        a, _ = draw(spec, seed=1)
        b, _ = draw(spec, seed=2)
        assert [e.anchor_id for e in a] != [e.anchor_id for e in b]

    def test_the_bank_has_the_planned_shape(self, spec) -> None:
        entries, _ = draw(spec)
        counts: dict[str, int] = {}
        for entry in entries:
            counts[entry.kind] = counts.get(entry.kind, 0) + 1
        assert counts[FACET_OUT] == 6 and counts[FACET_IN] == 6
        assert counts[HOMO_OUT] == 5 and counts[HOMO_IN] == 5
        assert counts[DESCRIBE] == 4
        assert counts[MULTIHOP] == 2 and counts[UNANSWERABLE] == 2
        assert len(entries) == 30

    def test_every_answerable_question_has_non_empty_gold(self, spec) -> None:
        """A facet question with empty gold measures abstention, not retrieval,
        and would silently dilute H1."""
        entries, _ = draw(spec)
        for entry in entries:
            if entry.kind == UNANSWERABLE:
                assert entry.expected_ids == []
            else:
                assert entry.expected_ids, entry.question_id

    def test_homogeneous_questions_really_are_homogeneous(self, spec) -> None:
        """H3's population must contain only same-label-both-ends edges."""
        entries, _ = draw(spec)
        for entry in entries:
            if entry.kind in (HOMO_OUT, HOMO_IN):
                assert entry.homogeneous is True
                assert entry.anchor_label == entry.neighbour_label

    def test_homogeneous_questions_never_use_an_inferred_edge(self, spec) -> None:
        """GROUP -MEMBER_OF-> GROUP is inferred AND homogeneous. H3 is a claim
        about ReliaQuest's schema, so it must not be measured over our own
        reconstruction."""
        entries, _ = draw(spec)
        for entry in entries:
            if entry.kind in (HOMO_OUT, HOMO_IN):
                assert entry.uses_inferred is False, entry.question_id

    def test_both_directions_are_represented(self, spec) -> None:
        entries, _ = draw(spec)
        directions = {e.direction for e in entries if e.edge}
        assert directions == {"out", "in"}

    def test_unanswerable_anchors_have_no_edges_at_all(self, spec) -> None:
        entries, _ = draw(spec)
        reachable = {t for r in spec.edges for t in (r["source_id"], r["target_id"])}
        for entry in entries:
            if entry.kind == UNANSWERABLE:
                assert entry.anchor_id not in reachable


class TestDirectionMatters:
    """The out and in readings of one edge must not collapse into each other --
    if they did, H3 could not fail."""

    def test_out_and_in_gold_differ_on_a_homogeneous_edge(self, spec) -> None:
        homo = [
            spec.triple_of(r)
            for r in spec.edges
            if r["origin"] == DECLARED and spec.triple_of(r)[0] == spec.triple_of(r)[2]
        ]
        assert homo
        source, edge, _target = homo[0]
        anchor = next(
            record["source_id"]
            for record in spec.edges
            if record["edge"] == edge
            and spec.label_of(record["source_id"]) == source
        )
        out = facet_gold(spec, anchor, edge, "out", "Q-out")
        inn = facet_gold(spec, anchor, edge, "in", "Q-in")
        assert set(out.expected_ids) != set(inn.expected_ids)


class TestTheAuthorIsBlind:
    def test_the_author_view_carries_only_four_fields(self, spec) -> None:
        entries, _ = draw(spec)
        for entry in entries:
            assert set(entry.author_view) <= {
                "label",
                "name",
                "relationship",
                "direction",
                "property",
                "value",
            }

    def test_the_prompt_never_contains_the_expected_answer(self, spec) -> None:
        """The single property that makes this bank blind."""
        entries, _ = draw(spec)
        for entry in entries:
            prompt = author_prompt(entry.author_view)
            for name in entry.expected_names:
                if name == entry.anchor_name:
                    continue  # the anchor itself is allowed; it is the question
                assert name not in prompt, f"{entry.question_id} leaks {name}"
            for node_id in entry.expected_ids:
                assert node_id not in prompt

    def test_the_prompt_does_not_leak_schema_vocabulary_as_instruction(self) -> None:
        assert "SCREAMING_CASE" in AUTHOR_SYSTEM  # it is told NOT to use it

    def test_authoring_resumes_from_a_checkpoint(self, spec, tmp_path: Path) -> None:
        """Contention on the shared server must cost one question, not the bank."""
        entries, _ = draw(spec)
        entries = entries[:5]
        checkpoint = tmp_path / "authored.json"
        calls = {"n": 0}

        def flaky(_system: str, _user: str) -> str:
            calls["n"] += 1
            if calls["n"] == 3:
                raise RuntimeError("server busy")
            return f"question {calls['n']}"

        with pytest.raises(RuntimeError):
            author_all(entries, flaky, checkpoint=checkpoint)
        assert checkpoint.is_file()
        partial = len(
            __import__("json").loads(checkpoint.read_text(encoding="utf-8"))
        )
        assert partial == 2

        authored = author_all(entries, lambda s, u: "recovered", checkpoint=checkpoint)
        assert len(authored) == 5
        # The two written before the failure are not re-authored.
        assert sum(1 for v in authored.values() if v == "recovered") == 3

    def test_an_empty_reply_is_not_recorded_as_a_question(self, spec, tmp_path: Path) -> None:
        """Recording "" would manufacture an unanswerable question by accident
        and quietly depress the score."""
        entries, _ = draw(spec)
        authored = author_all(entries[:3], lambda s, u: "   ")
        assert authored == {}


class TestCompiler:
    def test_unauthored_questions_are_discarded_not_repaired(self, spec) -> None:
        entries, _ = draw(spec)
        bank, discards = compile_bank(entries, {entries[0].question_id: "Q?"})
        assert len(bank["questions"]) == 1
        assert len(discards) == len(entries) - 1
        assert all(d["reason"] == "no authored text" for d in discards)

    def test_the_bank_carries_gold_and_the_protocol_statement(self, spec) -> None:
        entries, _ = draw(spec)
        authored = {e.question_id: f"Q for {e.question_id}?" for e in entries}
        bank, discards = compile_bank(entries, authored, author_model="test")
        assert not discards
        assert len(bank["questions"]) == 30
        sample = bank["questions"][entries[0].question_id]
        assert sample["expected_ids"] == sorted(entries[0].expected_ids)
        assert sample["split"] == "identity-blind"
        assert "blueprint" in bank["meta"]["protocol"]


class TestGoldIsIndependent:
    """Gold comes from the blueprint; answers come from the store. If the two
    disagree, the build or the load is wrong -- and this is the only test that
    can tell. Skips when no store is up."""

    @pytest.fixture(scope="class")
    def session(self):
        neo4j = pytest.importorskip("neo4j")
        uri = os.environ.get("IDENTITY_NEO4J_URI", "bolt://localhost:5459")
        user = os.environ.get("NEO4J_USER", "neo4j")
        password = os.environ.get("NEO4J_PASSWORD", "")
        try:
            driver = neo4j.GraphDatabase.driver(uri, auth=(user, password))
            driver.verify_connectivity()
        except Exception as exc:
            pytest.skip(f"identity store not reachable at {uri}: {exc}")
        with driver.session() as handle:
            yield handle
        driver.close()

    def test_spec_derived_gold_agrees_with_a_direct_graph_read(self, spec, session) -> None:
        entries, _ = draw(spec)
        checked = 0
        for entry in entries:
            if entry.kind in (DESCRIBE, MULTIHOP, UNANSWERABLE):
                continue
            # Scoped by neighbour label, exactly as the gold is: one edge name
            # spans several triples in this schema, so an unscoped read would
            # return a mixed-label neighbourhood and disagree for the wrong
            # reason.
            arrow = (
                f"(a)-[:{entry.edge}]->(b:{entry.neighbour_label})"
                if entry.direction == "out"
                else f"(b:{entry.neighbour_label})-[:{entry.edge}]->(a)"
            )
            rows = session.run(
                f"MATCH {arrow} WHERE a.id = $id RETURN collect(DISTINCT b.id) AS ids",
                id=entry.anchor_id,
            ).single()
            from_store = set(rows["ids"] or [])
            assert from_store == set(entry.expected_ids), (
                f"{entry.question_id}: blueprint and store disagree "
                f"({len(entry.expected_ids)} vs {len(from_store)})"
            )
            checked += 1
        assert checked >= 20, f"only {checked} facet questions cross-checked"

    def test_the_store_holds_exactly_what_the_blueprint_says(self, spec, session) -> None:
        counts = spec.counts()
        nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        edges = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        assert nodes == counts["nodes"]
        assert edges == counts["edges"]
