#!/usr/bin/env python3
"""Compile the authored question archetypes into committed bank JSON.

Regenerate with:
    uv run python -m utils.specialists.evalset.compile_banks
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .gold_bank import GOLDEN_DIR, load_gold_bank
from .questions import build_attack_questions, build_capec_questions

ATTACK_BANK_PATH = GOLDEN_DIR / "attack_questions.json"
CAPEC_BANK_PATH = GOLDEN_DIR / "capec_questions.json"


def compile_banks(gold: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    gold = gold or load_gold_bank()
    meta = {
        "attack_version": gold["meta"]["attack_version"],
        "capec_version": gold["meta"]["capec_version"],
        "gold_bank": "gold_bank.json",
        "generator": "utils/specialists/evalset/compile_banks.py",
    }
    attack_bank = {"meta": meta, "questions": build_attack_questions(gold)}
    capec_bank = {"meta": meta, "questions": build_capec_questions(gold)}
    return attack_bank, capec_bank


def load_bank(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile the golden question banks.")
    parser.add_argument("--out-dir", type=Path, default=GOLDEN_DIR)
    args = parser.parse_args()

    attack_bank, capec_bank = compile_banks()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for path, bank in (
        (args.out_dir / ATTACK_BANK_PATH.name, attack_bank),
        (args.out_dir / CAPEC_BANK_PATH.name, capec_bank),
    ):
        path.write_text(json.dumps(bank, indent=1) + "\n")
        print(f"wrote {path} ({len(bank['questions'])} questions)")


if __name__ == "__main__":
    main()
