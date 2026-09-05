#!/usr/bin/env python3
"""Assert the 288-question holdout is unspent, and cut it into its own bank.

"Sealed" has a precise meaning here and the loose version is wrong. The
deterministic arm **answered** all 288 on 2026-09-02 and its model-free recall
was published (`holdout 0.4683` against `dev 0.4350`) as evidence the bank had
not been tuned. That look was deliberate and is on the record. What has never
happened -- and is the property the holdout is actually being kept for -- is a
**judged** holdout, plus any holdout answer from the `generic` or `llm_query`
arms.

**The predecessor of this check did not work.** `scripts/overnight_two_track.py`
reads `id` off every file under `answers/`, but a judgment sidecar carries
`case_id` and has no `id` at all, so every sidecar fell out of the loop before
reaching the `.judgment` branch and the judged counter was **vacuously zero**.
The conclusion it reported happens to be true; the assertion behind it was not
being tested. This version keys answers on `id` and judgments on `case_id`, and
proves it is looking at something by asserting the *dev* half is judged --
a check that must find judgments, so a scan that silently sees nothing fails
loudly instead of passing quietly.

    uv run python scripts/holdout_seal.py --write-bank
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

BANK = REPO / "docs/evaluation/composition/bank/bank.json"
HOLDOUT_BANK = REPO / "docs/evaluation/composition/bank/bank-holdout.json"
RUNS = REPO / "docs/evaluation/experiments"

#: The set the dev/holdout split was drawn on. Any other bank is a different
#: experiment wearing this one's name.
EXPECTED_BANK_PREFIX = "ad99afb1"


def scan(splits: dict[str, str]) -> dict:
    answered: Counter[str] = Counter()
    judged: Counter[str] = Counter()
    dev_judged = 0
    unreadable = 0
    for path in RUNS.rglob("answers/*.json"):
        try:
            payload = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            unreadable += 1
            continue
        if ".judgment" in path.name:
            cid = payload.get("case_id")
            split = splits.get(cid)
            if split == "holdout":
                judged[f"{path.parent.parent.parent.name}/{path.parent.parent.name}"] += 1
            elif split == "dev":
                dev_judged += 1
            continue
        cid = payload.get("id")
        if splits.get(cid) == "holdout":
            answered[path.parent.parent.name] += 1
    return {"answered_by_arm": dict(answered), "judged_by_run": dict(judged),
            "dev_judgments_seen": dev_judged, "unreadable_files": unreadable}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-bank", action="store_true")
    # Step 7 SPENDS the holdout, so "only deterministic has answered" stops being
    # true the moment the sanctioned run starts. That is not a breach and the
    # guard must not block the very run it was written for. What stays absolute
    # is the property the holdout is actually kept for: ZERO judgments.
    ap.add_argument("--sanctioned-arms", nargs="*", default=["deterministic"],
                    help="arms EXP-2026-09-007 permits to have answered the holdout")
    ap.add_argument("--allow-judged", action="store_true",
                    help="only after judging has deliberately begun; never by default")
    args = ap.parse_args()

    digest = hashlib.sha256(BANK.read_bytes()).hexdigest()
    bank = json.loads(BANK.read_text())
    questions = bank["questions"]
    splits = {q["id"]: q["split"] for q in questions}
    holdout = [q for q in questions if q["split"] == "holdout"]

    # The holdout half hashed on its own, so a later run can prove the questions
    # it answered are the questions that were sealed today.
    canon = json.dumps(holdout, sort_keys=True, separators=(",", ":")).encode()
    holdout_digest = hashlib.sha256(canon).hexdigest()

    report = {
        "bank_sha256": digest,
        "bank_is_the_split_set": digest.startswith(EXPECTED_BANK_PREFIX),
        "n_dev": sum(1 for q in questions if q["split"] == "dev"),
        "n_holdout": len(holdout),
        "holdout_questions_sha256": holdout_digest,
        **scan(splits),
    }
    sanctioned = set(args.sanctioned_arms)
    report["sanctioned_arms"] = sorted(sanctioned)
    report["unsanctioned_answers"] = sorted(set(report["answered_by_arm"]) - sanctioned)
    # Two separate properties, deliberately not conflated:
    #   unjudged  -- the one the holdout exists to protect
    #   pristine  -- nothing but `deterministic` has ever answered it
    report["unjudged"] = not report["judged_by_run"]
    report["pristine"] = not (set(report["answered_by_arm"]) - {"deterministic"})
    report["sealed"] = (
        report["unjudged"]
        and not report["unsanctioned_answers"]
        and report["bank_is_the_split_set"]
    )
    print(json.dumps(report, indent=1))

    if not report["bank_is_the_split_set"]:
        raise SystemExit(f"bank.json sha256 {digest[:12]} is not the split set")
    # A scan that finds nothing looks identical to a scan that is broken. The
    # dev half MUST be judged -- if this is zero the scan is not working and the
    # holdout result below means nothing.
    if report["dev_judgments_seen"] == 0:
        raise SystemExit("scan found zero dev judgments — the scan is broken, "
                         "not the holdout clean")
    if report["judged_by_run"] and not args.allow_judged:
        raise SystemExit(f"HOLDOUT ALREADY JUDGED: {report['judged_by_run']}")
    if report["unsanctioned_answers"]:
        raise SystemExit(f"arms {report['unsanctioned_answers']} have answered "
                         "holdout questions and are not sanctioned by "
                         "EXP-2026-09-007")

    if args.write_bank:
        out = {"meta": {**bank["meta"],
                        "split": "holdout only, cut from bank.json",
                        "source_bank_sha256": digest,
                        "holdout_questions_sha256": holdout_digest},
               "questions": holdout}
        HOLDOUT_BANK.write_text(json.dumps(out, indent=1) + "\n")
        print(f"\nwrote {HOLDOUT_BANK} ({len(holdout)} questions)")
    print("\nSEALED" if report["sealed"] else "\nNOT SEALED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
