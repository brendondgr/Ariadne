#!/usr/bin/env python3
"""Unit tests for the research-record tooling.

The validator is only worth having if it fails on the things it claims to fail
on, so each of the eight conditions in section 7.3 gets a test that breaks a
valid fixture in exactly one way and asserts the specific check fires. Tests run
against fixtures under ``tmp_path``, never against the real corpus — a test that
mutated ``docs/research/`` would violate the append-only rule it is defending.
"""

from __future__ import annotations

import datetime as _dt
import shutil
from pathlib import Path

import pytest
import yaml

from utils.research_record import paths as rr_paths
from utils.research_record.manifest import ManifestError, load_manifest
from utils.research_record.scaffold import ScaffoldError, next_id, scaffold
from utils.research_record.validate import Finding, validate_experiment

FIXTURES = Path(__file__).parent / "fixtures"
VALID = FIXTURES / "EXP-2000-01-001-valid-fixture"


def _checks(findings: list[Finding]) -> set[str]:
    return {f.check for f in findings}


@pytest.fixture
def experiment(tmp_path: Path) -> Path:
    """A copy of the valid fixture that a test may break freely."""
    target = tmp_path / VALID.name
    shutil.copytree(VALID, target)
    return target


def _edit_manifest(exp: Path, mutate) -> None:
    path = exp / "manifest.yaml"
    data = yaml.safe_load(path.read_text())
    mutate(data)
    path.write_text(yaml.safe_dump(data, sort_keys=False))


# --- the fixture itself -----------------------------------------------------


def test_valid_fixture_passes(experiment: Path) -> None:
    assert validate_experiment(experiment, claim_ids={"C-001"}) == []


def test_manifest_round_trips(experiment: Path) -> None:
    manifest = load_manifest(experiment / "manifest.yaml")
    assert manifest.id == "EXP-2000-01-001"
    assert manifest.slug == "valid-fixture"
    assert manifest.is_terminal
    assert manifest.primary_value == pytest.approx(0.5)


# --- condition 1: required files --------------------------------------------


@pytest.mark.parametrize("name", ["manifest.yaml", "PROTOCOL.md", "RESULTS.md"])
def test_missing_required_file_fails(experiment: Path, name: str) -> None:
    (experiment / name).unlink()
    findings = validate_experiment(experiment, claim_ids={"C-001"})
    assert "required-files" in _checks(findings)
    assert any(name in f.detail for f in findings)


# --- condition 2: schema ----------------------------------------------------


def test_schema_violation_fails(experiment: Path) -> None:
    _edit_manifest(experiment, lambda d: d.__setitem__("status", "mostly-done"))
    assert "schema" in _checks(validate_experiment(experiment, claim_ids={"C-001"}))


def test_unknown_field_is_rejected(experiment: Path) -> None:
    """extra='forbid' — a typo'd field must not be silently ignored."""
    _edit_manifest(experiment, lambda d: d.__setitem__("hypothesus", "typo"))
    assert "schema" in _checks(validate_experiment(experiment, claim_ids={"C-001"}))


def test_missing_reproducibility_block_fails(experiment: Path) -> None:
    _edit_manifest(experiment, lambda d: d.pop("code"))
    assert "schema" in _checks(validate_experiment(experiment, claim_ids={"C-001"}))


def test_unknown_commit_is_accepted(experiment: Path) -> None:
    """Back-fill honesty: 'unknown' validates, so nobody has to invent a sha."""
    _edit_manifest(experiment, lambda d: d["code"].__setitem__("commit", "unknown"))
    assert validate_experiment(experiment, claim_ids={"C-001"}) == []


def test_malformed_hash_fails(experiment: Path) -> None:
    _edit_manifest(experiment, lambda d: d["data"].__setitem__("hash", "deadbeef"))
    assert "schema" in _checks(validate_experiment(experiment, claim_ids={"C-001"}))


def test_id_must_match_directory(experiment: Path) -> None:
    _edit_manifest(experiment, lambda d: d.__setitem__("slug", "different-slug"))
    assert "id-mismatch" in _checks(validate_experiment(experiment, claim_ids={"C-001"}))


# --- condition 3: complete with no metrics ----------------------------------


def test_complete_with_empty_metrics_fails(experiment: Path) -> None:
    _edit_manifest(experiment, lambda d: d["metrics"].__setitem__("values", {}))
    assert "empty-metrics" in _checks(validate_experiment(experiment, claim_ids={"C-001"}))


def test_planned_with_empty_metrics_passes(experiment: Path) -> None:
    """A planned experiment legitimately has no numbers yet."""

    def mutate(d: dict) -> None:
        d["status"] = "planned"
        d["date_completed"] = None
        d["metrics"]["values"] = {}

    _edit_manifest(experiment, mutate)
    assert "empty-metrics" not in _checks(validate_experiment(experiment, claim_ids={"C-001"}))


# --- conditions 4 and 5: figures --------------------------------------------


def test_declared_figure_without_file_fails(experiment: Path) -> None:
    (experiment / "figures" / "fig-demo.svg").unlink()
    assert "figure-missing" in _checks(validate_experiment(experiment, claim_ids={"C-001"}))


def test_figure_file_not_declared_fails(experiment: Path) -> None:
    (experiment / "figures" / "fig-orphan.svg").write_text("<svg/>")
    assert "figure-unlisted" in _checks(validate_experiment(experiment, claim_ids={"C-001"}))


def test_figure_without_generator_fails(experiment: Path) -> None:
    (experiment / "figures" / "make_figures.py").unlink()
    assert "figure-no-generator" in _checks(validate_experiment(experiment, claim_ids={"C-001"}))


# --- condition 6: pointers --------------------------------------------------


def test_pointer_without_hash_fails(experiment: Path) -> None:
    pointers = experiment / "data" / "POINTERS.md"
    pointers.write_text(
        pointers.read_text() + "| run-output | docs/evaluation/x | 10 | | raw answers |\n"
    )
    assert "pointer-no-hash" in _checks(validate_experiment(experiment, claim_ids={"C-001"}))


def test_pointer_with_hash_passes(experiment: Path) -> None:
    pointers = experiment / "data" / "POINTERS.md"
    pointers.write_text(
        pointers.read_text()
        + f"| run-output | docs/evaluation/x | 10 | sha256:{'a' * 64} | raw answers |\n"
    )
    assert "pointer-no-hash" not in _checks(validate_experiment(experiment, claim_ids={"C-001"}))


# --- condition 7: claim linkage ---------------------------------------------


def test_unknown_claim_fails(experiment: Path) -> None:
    findings = validate_experiment(experiment, claim_ids=set())
    assert "unknown-claim" in _checks(findings)
    assert any("C-001" in f.detail for f in findings)


# --- scaffolding ------------------------------------------------------------


def test_scaffold_produces_a_validating_folder(tmp_path: Path, monkeypatch) -> None:
    """`make new-experiment` must scaffold something the validator accepts."""
    experiments = tmp_path / "experiments"
    experiments.mkdir()
    monkeypatch.setattr(rr_paths, "EXPERIMENTS_ROOT", experiments)
    monkeypatch.setattr("utils.research_record.scaffold.EXPERIMENTS_ROOT", experiments)

    target = scaffold("demo-experiment", when=_dt.date(2026, 8, 6))

    assert target.name == "EXP-2026-08-001-demo-experiment"
    for name in ("manifest.yaml", "PROTOCOL.md", "RESULTS.md", "ISSUES.md"):
        assert (target / name).is_file()

    manifest = load_manifest(target / "manifest.yaml")
    assert manifest.id == "EXP-2026-08-001"
    assert manifest.slug == "demo-experiment"
    assert manifest.status == "planned"
    assert manifest.date_started == _dt.date(2026, 8, 6)
    # Provenance captured at scaffold time, not left as a placeholder.
    assert manifest.code.commit != "unknown"
    assert len(manifest.code.commit) == 40

    assert validate_experiment(target, claim_ids=set()) == []


def test_next_id_increments_and_never_reuses(tmp_path: Path, monkeypatch) -> None:
    experiments = tmp_path / "experiments"
    experiments.mkdir()
    monkeypatch.setattr("utils.research_record.scaffold.EXPERIMENTS_ROOT", experiments)

    assert next_id(_dt.date(2026, 8, 6)) == "EXP-2026-08-001"
    (experiments / "EXP-2026-08-001-a").mkdir()
    (experiments / "EXP-2026-08-004-b").mkdir()
    # max+1, not count+1: a gap is never recycled into a published ID.
    assert next_id(_dt.date(2026, 8, 6)) == "EXP-2026-08-005"
    # Numbering is per month.
    assert next_id(_dt.date(2026, 9, 1)) == "EXP-2026-09-001"


def test_scaffold_rejects_a_bad_slug(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("utils.research_record.scaffold.EXPERIMENTS_ROOT", tmp_path)
    with pytest.raises(ScaffoldError, match="kebab-case"):
        scaffold("Not A Slug")


# --- index ------------------------------------------------------------------


def test_index_is_deterministic() -> None:
    from utils.research_record.index import render_index

    assert render_index() == render_index()


def test_index_lists_every_experiment() -> None:
    from utils.research_record.index import render_index

    rendered = render_index()
    for exp in rr_paths.experiment_dirs():
        assert exp.name in rendered, f"{exp.name} missing from INDEX.md"


# --- hashing ----------------------------------------------------------------


def test_hashing_is_stable_and_content_sensitive(tmp_path: Path) -> None:
    from utils.research_record.hashing import sha256_file, sha256_tree

    target = tmp_path / "a.json"
    target.write_text('{"x": 1}')
    first = sha256_file(target)
    assert first == sha256_file(target)
    assert first.startswith("sha256:")

    target.write_text('{"x": 2}')
    assert sha256_file(target) != first

    tree_hash = sha256_tree(tmp_path)
    (tmp_path / "b.json").write_text("{}")
    assert sha256_tree(tmp_path) != tree_hash


def test_load_manifest_names_the_offending_file(tmp_path: Path) -> None:
    bad = tmp_path / "manifest.yaml"
    bad.write_text("just a string")
    with pytest.raises(ManifestError, match="manifest.yaml"):
        load_manifest(bad)
