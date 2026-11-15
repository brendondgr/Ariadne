#!/usr/bin/env python3
"""EXP-2026-11-007: replay the era-2 reply-repair layer over every saved kill-test reply.

No model calls. For each saved generation in the typed kill tests' caches, the
old parser (``utils.killtests.typed.prompts.extract_request``) and the new layer
(``utils.llm.repair.extract_json_object``) both read the reply; the counts in
``PROTOCOL.md`` are computed per cache file, model and arm family.

    uv run python scripts/era2_repair_replay.py --out <experiment>/data
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.killtests.typed.prompts import extract_request  # noqa: E402
from utils.llm.repair import extract_json_object, split_thinking  # noqa: E402

BASE = REPO / "logs" / "killtests-2026-11"
CACHES = [
    ("EXP-2026-11-004", "typed/cache/generate.jsonl"),
    ("EXP-2026-11-005", "exp005/cache/A-generate.jsonl"),
    ("EXP-2026-11-005", "exp005/cache/A-repair.jsonl"),
    ("EXP-2026-11-005", "exp005/cache/B-generate.jsonl"),
    ("EXP-2026-11-005", "exp005/cache/B-repair.jsonl"),
    ("EXP-2026-11-005 (xhigh archive)", "exp005/cache/B-generate.qwen-xhigh-archive.jsonl"),
    ("EXP-2026-11-006", "exp006/cache/A-generate.jsonl"),
    ("EXP-2026-11-006", "exp006/cache/A-repair.jsonl"),
    ("EXP-2026-11-006", "exp006/cache/B-generate.jsonl"),
    ("EXP-2026-11-006", "exp006/cache/B-repair.jsonl"),
    ("EXP-2026-11-006", "exp006/cache/C-generate.jsonl"),
    ("EXP-2026-11-006", "exp006/cache/C-repair.jsonl"),
]


def _old(raw: str):
    try:
        v = extract_request(raw)
    except (ValueError, json.JSONDecodeError):
        return None
    return v if isinstance(v, dict) else None


def _plain(raw: str):
    try:
        v = json.loads(raw.strip())
    except ValueError:
        return None
    return v if isinstance(v, dict) else None


def replay(cap_aware: bool = True) -> tuple[list[dict], list[dict]]:
    cells: dict[tuple, Counter] = defaultdict(Counter)
    kinds: dict[tuple, Counter] = defaultdict(Counter)
    examples: dict[tuple, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    rescued_rows: list[dict] = []
    for exp, rel in CACHES:
        path = BASE / rel
        if not path.exists():
            raise SystemExit(f"missing cache {path}")
        seen: set[str] = set()
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            key = rec["key"]
            if key in seen:            # a cache may hold a key twice after a resume; count once
                continue
            seen.add(key)
            val = rec.get("value") or {}
            parts = key.split("|")
            arm, model = parts[1], parts[2]
            family = "typed" if arm.startswith("typed") else "free"
            cell = (exp, rel, model, family)
            raw = val.get("raw") or ""
            capped = val.get("finish_reason") == "length"
            c = cells[cell]
            c["n"] += 1
            c["capped"] += capped
            _, text, _ = split_thinking(raw)
            c["empty"] += not text.strip()
            if family == "free":
                continue
            old = _old(raw)
            new = extract_json_object(raw, cut_off=capped and cap_aware)
            c["old_ok"] += old is not None
            c["new_ok"] += new.value is not None
            c["still_invalid"] += new.value is None
            if old is not None and new.value is not None and old != new.value:
                c["changed"] += 1
                examples[cell]["changed"].append(key)
            plain = _plain(raw)
            if new.value is not None and new.value != plain and not new.events:
                c["silent"] += 1
                examples[cell]["silent"].append(key)
            if new.value is not None and old is None:
                c["rescued"] += 1
                c["capped_rescued"] += capped
                ks = sorted({e.kind for e in new.events})
                for k in ks:
                    kinds[cell][k] += 1
                    if len(examples[cell][k]) < 5:
                        examples[cell][k].append(key)
                rescued_rows.append({"experiment": exp, "cache": rel, "key": key, "capped": capped,
                                     "repairs": ks, "recovered": new.value})
            if new.value is None and capped:
                c["capped_still_invalid"] += 1
    rows = []
    for cell, c in cells.items():
        exp, rel, model, family = cell
        rows.append({"experiment": exp, "cache": rel, "model": model, "family": family, **dict(c),
                     "rescued_by_kind": dict(kinds[cell]),
                     "examples": {k: v[:5] for k, v in examples[cell].items()}})
    rows.sort(key=lambda r: (r["cache"], r["model"], r["family"]))
    return rows, rescued_rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-cap-aware", action="store_true",
                    help="close truncated JSON even in capped replies (the pre-registered run's policy)")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows, rescued = replay(cap_aware=not args.no_cap_aware)
    totals = Counter()
    for r in rows:
        for k in ("n", "capped", "empty", "old_ok", "new_ok", "rescued", "changed", "silent",
                  "still_invalid", "capped_rescued", "capped_still_invalid"):
            totals[k] += r.get(k, 0)
    tag = "" if not args.no_cap_aware else "-preregistered"
    policy = "cap-aware" if not args.no_cap_aware else "close-always"
    (out / f"replay{tag}.json").write_text(json.dumps(
        {"policy": policy, "cells": rows, "totals": dict(totals)}, indent=1))
    with open(out / f"rescued{tag}.jsonl", "w") as fh:
        for r in rescued:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    cols = ["n", "capped", "empty", "old_ok", "new_ok", "rescued", "changed", "silent", "still_invalid",
            "capped_rescued"]
    print("cache  model  family  " + "  ".join(cols) + "  rescued_by_kind")
    for r in rows:
        print(f"{r['cache']}  {r['model']}  {r['family']}  "
              + "  ".join(str(r.get(k, 0)) for k in cols) + f"  {r['rescued_by_kind']}")
    print("TOTAL", dict(totals))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
