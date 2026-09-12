#!/usr/bin/env python3
"""Prove a bank is unspent before anything is allowed to run against it.

    uv run python scripts/fresh_seal.py --bank docs/evaluation/composition/bank/bank-fresh-2026-09-12.json
    uv run python scripts/fresh_seal.py --self-test     # it must be able to FAIL

`scripts/holdout_seal.py` generalised. That script hard-codes the split bank it
was written for — `EXPECTED_BANK_PREFIX`, `bank.json`, the dev/holdout split —
so it cannot be pointed at a newly minted set, which is exactly what Step 7
needs.

**A seal check that cannot fail is not a check.** Its own predecessor
(`overnight_two_track.py`) read `id` off every file under `answers/`; a judgment
sidecar carries `case_id` and no `id`, so every sidecar fell out of the loop
before reaching the judged branch and the judged counter was **vacuously zero**.
The conclusion happened to be true and the assertion behind it was never tested.
So this one carries `--self-test`, which points it at `bank-holdout.json` —
a bank with thousands of judgments — and requires it to come back NOT SEALED.
If the check cannot fail on a spent bank it is not trusted on a fresh one.

The report is written into `EXP-2026-09-018/data/POINTERS.md` **before** the
first arm runs, so a later reader can prove the questions that were answered are
the questions that were sealed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

RUNS = REPO / "docs/evaluation/experiments"
HOLDOUT_BANK = REPO / "docs/evaluation/composition/bank/bank-holdout.json"
#: A scan that finds nothing looks identical to a scan that is broken, so the
#: scan must also find something it KNOWS is there. The development half is
#: judged many times over; if this count is zero the scan is broken.
CONTROL_BANK = REPO / "docs/evaluation/composition/bank/bank-dev.json"


def _ids(bank: Path) -> set[str]:
    doc = json.loads(bank.read_text())
    questions = doc["questions"] if isinstance(doc, dict) else doc
    return {str(q["id"]) for q in questions}


def scan(target: set[str], control: set[str]) -> dict:
    """Every answer and judgment anywhere under the runs tree, by bank."""
    answered: Counter[str] = Counter()
    judged: Counter[str] = Counter()
    control_judged = 0
    unreadable = 0
    for path in RUNS.rglob("answers/*.json"):
        try:
            payload = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            unreadable += 1
            continue
        cell = f"{path.parent.parent.parent.name}/{path.parent.parent.name}"
        if ".judgment" in path.name:
            case = payload.get("case_id")
            if case in target:
                judged[cell] += 1
            elif case in control:
                control_judged += 1
            continue
        if payload.get("id") in target:
            answered[cell] += 1
    return {
        "answered_by_cell": dict(answered),
        "judged_by_cell": dict(judged),
        "control_judgments_seen": control_judged,
        "unreadable_files": unreadable,
    }


def seal(bank: Path) -> dict:
    doc = json.loads(bank.read_text())
    questions = doc["questions"] if isinstance(doc, dict) else doc
    target = {str(q["id"]) for q in questions}
    canon = json.dumps(questions, sort_keys=True, separators=(",", ":")).encode()
    report = {
        "bank": str(bank.relative_to(REPO)),
        "bank_sha256": hashlib.sha256(bank.read_bytes()).hexdigest(),
        "questions_sha256": hashlib.sha256(canon).hexdigest(),
        "n": len(questions),
        "tiers": dict(sorted(Counter(str(q["id"]).split("-")[0] for q in questions).items())),
        **scan(target, _ids(CONTROL_BANK) - target),
    }
    report["unanswered"] = not report["answered_by_cell"]
    report["unjudged"] = not report["judged_by_cell"]
    report["scan_is_working"] = report["control_judgments_seen"] > 0
    report["sealed"] = (
        report["unanswered"] and report["unjudged"] and report["scan_is_working"]
    )
    return report


def self_test() -> int:
    """Point it at a spent bank. It must come back NOT SEALED, for the right reason."""
    report = seal(HOLDOUT_BANK)
    print(json.dumps({k: v for k, v in report.items()
                      if k != "answered_by_cell"}, indent=1))
    if report["sealed"]:
        print("SELF-TEST FAILED: a bank with judgments came back sealed")
        return 1
    if not report["scan_is_working"]:
        print("SELF-TEST FAILED: the scan saw no control judgments — it is broken")
        return 1
    if not report["judged_by_cell"]:
        print("SELF-TEST FAILED: the holdout is judged, and the scan did not see it")
        return 1
    print(f"SELF-TEST PASSED: the spent bank is refused, on "
          f"{sum(report['judged_by_cell'].values())} judgments across "
          f"{len(report['judged_by_cell'])} cells")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bank", default=None)
    ap.add_argument("--self-test", action="store_true",
                    help="prove the check can fail, on a bank that is spent")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if not args.bank:
        ap.error("--bank or --self-test")

    report = seal(Path(args.bank))
    print(json.dumps(report, indent=1))
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    if not report["scan_is_working"]:
        raise SystemExit("the scan saw zero control judgments — it is broken, "
                         "not the bank clean")
    if not report["sealed"]:
        raise SystemExit(f"NOT SEALED: answered={report['answered_by_cell']} "
                         f"judged={report['judged_by_cell']}")
    print("\nSEALED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
