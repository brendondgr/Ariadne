"""Builder backup-and-replace: a pre-existing canonical dir is backed up, not merged."""

from __future__ import annotations

import json
from pathlib import Path

from utils.kg_builder.main import KGBuildRunner
from utils.kg_builder.validate import validate_canonical_artifacts

FIXTURES = Path(__file__).parent / "fixtures"


def _seed_capec_raw(data_dir: Path) -> None:
    raw_dir = data_dir / "raw" / "capec" / "v3.9"
    raw_dir.mkdir(parents=True)
    (raw_dir / "capec_latest.xml").write_text(
        (FIXTURES / "minimal_capec_catalog.xml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (data_dir / "versions.json").write_text(
        json.dumps({"attack_version": "19.0", "capec_version": "3.9"}),
        encoding="utf-8",
    )


def test_build_backs_up_stale_canonical_and_rebuilds_clean(tmp_path: Path) -> None:
    _seed_capec_raw(tmp_path)

    canonical_dir = tmp_path / "graphs" / "capec" / "canonical"
    canonical_dir.mkdir(parents=True)
    # A stale leftover (e.g. a relationships file with a type the new schema
    # no longer allows) plus an orphan file that a clean rebuild must drop.
    (canonical_dir / "relationships.jsonl").write_text(
        json.dumps({"id": "r1", "type": "authored", "source_id": "a", "target_id": "b"}) + "\n",
        encoding="utf-8",
    )
    (canonical_dir / "orphan.txt").write_text("leftover", encoding="utf-8")

    KGBuildRunner(data_dir=str(tmp_path)).build_capec()

    # The stale leftovers were moved aside, not merged into the new build.
    assert not (canonical_dir / "orphan.txt").exists()
    backups = list((tmp_path / "graphs" / "capec" / "_backups").glob("canonical-*"))
    assert len(backups) == 1
    assert (backups[0] / "orphan.txt").read_text(encoding="utf-8") == "leftover"

    # The rebuilt canonical artifacts are internally consistent.
    result = validate_canonical_artifacts(canonical_dir)
    assert result["nodes"] > 0


def test_build_creates_no_backup_on_first_run(tmp_path: Path) -> None:
    _seed_capec_raw(tmp_path)

    KGBuildRunner(data_dir=str(tmp_path)).build_capec()

    assert not (tmp_path / "graphs" / "capec" / "_backups").exists()
    validate_canonical_artifacts(tmp_path / "graphs" / "capec" / "canonical")
