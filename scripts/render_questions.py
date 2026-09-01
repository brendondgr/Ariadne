#!/usr/bin/env python3
"""Render composition specs into natural questions (Step 4).

The model's only job is phrasing. It never sees the gold, the path, the tier, or
anything named after the system under test — see `utils.specialists.evalset.render`
for what a brief contains and why.

Every rendering is validated before it is kept, and every rejection is recorded
with its reason. A pipeline that silently re-rolled until something passed would
report a clean bank and hide how hard it had to work for it.

Usage:
    uv run python scripts/render_questions.py --limit 40 --model opencode/nemotron-3-ultra-free
    uv run python scripts/render_questions.py --tiers D5,D6 --registers analyst,indirect
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from utils.specialists.evalset import render as rd
from utils.specialists.evalset.author import AuthorConfig, AuthorUnavailable, _post, workers_for
from utils.specialists.evalset.composition import Filter, Spec, Step

DEFAULT_SPECS = Path("docs/evaluation/composition/attack-19.0-capec-3.9/specs.json")


def load_specs(path: Path) -> list[Spec]:
    payload = json.loads(path.read_text())
    specs: list[Spec] = []
    for raw in payload["specs"]:
        raw = dict(raw)
        raw["steps"] = tuple(Step(**s) for s in raw["steps"])
        raw["filters"] = tuple(Filter(**f) for f in raw["filters"])
        for key in ("gold", "shapes", "dangling"):
            raw[key] = tuple(raw.get(key) or ())
        raw.pop("query", None)
        specs.append(Spec(**raw, query={}))
    return specs


def _stratified(specs: list[Spec], limit: int, seed: int) -> list[Spec]:
    """Take `limit` specs spread across tiers rather than off the top.

    Specs are sorted by tier, so a plain head() would render only D0 and tell us
    nothing about the tiers we most need to see.
    """
    import random

    by_tier: dict[str, list[Spec]] = defaultdict(list)
    for spec in specs:
        by_tier[spec.tier].append(spec)
    rng = random.Random(seed)
    per = max(1, limit // max(1, len(by_tier)))
    out: list[Spec] = []
    for tier in sorted(by_tier):
        pool = by_tier[tier]
        out.extend(rng.sample(pool, min(per, len(pool))))
    return sorted(out, key=lambda s: (s.tier, s.id))[:limit]


def render_one(spec: Spec, register: str, config: AuthorConfig, attempts: int) -> dict[str, Any]:
    prompt = rd.prompt_for(rd.brief_for(spec), register)
    rejected: list[str] = []
    for _ in range(attempts):
        text = _post(config, prompt)
        # Reasoning models sometimes wrap the answer; the bare question lands on
        # the last non-empty line.
        candidate = next(
            (line.strip().strip('"') for line in reversed(text.splitlines()) if line.strip()),
            "",
        )
        reason = rd.rejection_reason(candidate, spec)
        if reason is None:
            return {
                "spec_id": spec.id,
                "tier": spec.tier,
                "register": register,
                "question": candidate,
                "schema_overlap": rd.schema_overlap(candidate, spec),
                "rejected_attempts": rejected,
                "ok": True,
            }
        rejected.append(f"{reason} :: {candidate[:120]}")
    return {
        "spec_id": spec.id,
        "tier": spec.tier,
        "register": register,
        "question": None,
        "rejected_attempts": rejected,
        "ok": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--specs", type=Path, default=DEFAULT_SPECS)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--model", default="opencode/nemotron-3-ultra-free")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--seed", type=int, default=20260901)
    parser.add_argument("--tiers", default=None)
    parser.add_argument("--registers", default=",".join(rd.REGISTERS))
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--max-tokens", type=int, default=4096)
    args = parser.parse_args()

    specs = load_specs(args.specs)
    if args.tiers:
        wanted = {t.strip() for t in args.tiers.split(",")}
        specs = [s for s in specs if s.tier in wanted]
    specs = [s for s in specs if rd.renderable(s)]
    if args.limit:
        specs = _stratified(specs, args.limit, args.seed)
    registers = [r.strip() for r in args.registers.split(",") if r.strip() in rd.REGISTERS]

    config = AuthorConfig(
        base_url=args.base_url or AuthorConfig.base_url,
        model=args.model,
        max_tokens=args.max_tokens,
    )
    jobs = [(spec, register) for spec in specs for register in registers]
    workers = workers_for(args.model, args.workers)
    print(f"[render] {len(specs)} specs x {len(registers)} registers = {len(jobs)} calls "
          f"on {args.model} with {workers} worker(s)")

    results: list[dict[str, Any]] = []
    done = 0
    started = time.time()

    def one(job: tuple[Spec, str]) -> None:
        nonlocal done
        spec, register = job
        try:
            results.append(render_one(spec, register, config, args.attempts))
        except AuthorUnavailable as exc:
            results.append(
                {"spec_id": spec.id, "tier": spec.tier, "register": register,
                 "question": None, "rejected_attempts": [f"unavailable: {exc}"], "ok": False}
            )
        done += 1
        if done % 10 == 0 or done == len(jobs):
            rate = done / max(1e-9, time.time() - started)
            print(f"[render] {done}/{len(jobs)} ({rate:.1f}/s)", flush=True)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, jobs))

    results.sort(key=lambda r: (r["tier"], r["spec_id"], r["register"]))
    kept = [r for r in results if r["ok"]]
    reasons = Counter(
        attempt.split(" :: ")[0].split(":")[0]
        for r in results
        for attempt in r["rejected_attempts"]
    )
    overlaps = sorted(r["schema_overlap"] for r in kept)
    report = {
        "model": args.model,
        "seed": args.seed,
        "registers": registers,
        "specs": len(specs),
        "calls": len(jobs),
        "kept": len(kept),
        "keep_rate": round(len(kept) / len(jobs), 4) if jobs else 0.0,
        "retried_but_kept": sum(1 for r in kept if r["rejected_attempts"]),
        "rejection_reasons": dict(reasons.most_common()),
        "by_tier": {
            tier: round(
                sum(1 for r in results if r["tier"] == tier and r["ok"])
                / max(1, sum(1 for r in results if r["tier"] == tier)),
                4,
            )
            for tier in sorted({r["tier"] for r in results})
        },
        "schema_overlap": {
            "mean": round(statistics.fmean(overlaps), 4) if overlaps else None,
            "median": round(statistics.median(overlaps), 4) if overlaps else None,
            "p90": overlaps[int(0.9 * (len(overlaps) - 1))] if overlaps else None,
            "max": overlaps[-1] if overlaps else None,
            "by_register": {
                reg: round(
                    statistics.fmean([r["schema_overlap"] for r in kept if r["register"] == reg]),
                    4,
                )
                for reg in registers
                if any(r["register"] == reg for r in kept)
            },
        },
        "wall_s": round(time.time() - started, 1),
    }

    out = args.out or args.specs.parent / "rendered.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"report": report, "questions": results}, indent=1) + "\n")

    print(f"\nrendered -> {out}")
    print(f"  kept {report['kept']}/{report['calls']} ({report['keep_rate']:.1%}) "
          f"in {report['wall_s']}s; {report['retried_but_kept']} needed a retry")
    print(f"  keep rate by tier: {report['by_tier']}")
    print(f"  rejections: {report['rejection_reasons'] or 'none'}")
    ov = report["schema_overlap"]
    print(f"  schema overlap: median {ov['median']}, p90 {ov['p90']}, max {ov['max']}")
    print(f"  by register: {ov['by_register']}")


if __name__ == "__main__":
    main()
