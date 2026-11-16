#!/usr/bin/env python3
"""EXP-2026-11-009: harness attribution (Era 2, Step 4).

    uv run python scripts/harness_attribution.py rerun   --root <runs root>
    uv run python scripts/harness_attribution.py code    --out <experiment>/data [--rerun-root <runs root>]
    uv run python scripts/harness_attribution.py packets --out <experiment>/data
    uv run python scripts/harness_attribution.py agree   --out <experiment>/data

``rerun`` runs the three model-free arms back to back, each in its own process
under a socket guard that refuses (and counts) any connection to a model port.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import socket
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.evaluation import harness_attribution as H  # noqa: E402

BANK = "docs/evaluation/composition/bank/bank-dev.json"
RERUN_ARMS = ("generic_composed", "generic_composed_capped", "generic_planned")
MODEL_PORTS = {9090, 4000, 7070, 7500}
SEED = 20261115


# --------------------------------------------------------------------------- #
# rerun: three model-free arms, guarded at the socket
# --------------------------------------------------------------------------- #


def _install_guard(record: Path) -> None:
    attempts: list[str] = []
    real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex

    def check(addr) -> None:
        if isinstance(addr, tuple) and len(addr) >= 2 and int(addr[1]) in MODEL_PORTS:
            attempts.append(f"{addr[0]}:{addr[1]}")
            record.write_text(json.dumps({"attempts": attempts}))
            raise ConnectionRefusedError(f"model-free guard: refused {addr}")

    def connect(self, addr):
        check(addr)
        return real_connect(self, addr)

    def connect_ex(self, addr):
        check(addr)
        return real_connect_ex(self, addr)

    socket.socket.connect, socket.socket.connect_ex = connect, connect_ex
    record.write_text(json.dumps({"attempts": attempts}))


def _llm_arm(arm: str, root: str, workers: int) -> int:
    """A-1: the LLM-planner arm, unguarded (it calls the model), at the registry's thinking level."""
    from utils.evaluation import experiment_untruncated as exp

    return exp.main(["--arm", arm, "--root", root, "--bank", BANK, "--workers", str(workers),
                     "--llm-model", "default-model"])


def rerun_qwen(root: str, workers: int) -> None:
    """EXP-2026-11-009 A-1: composed, planned (guarded), then the Qwen planner arm, back to back."""
    from utils.llm.registry import load, require_identity

    spec = load().default
    if spec.name != "qwen38-27b":
        raise SystemExit(f"registry default is {spec.name}, not qwen38-27b")
    before = require_identity(spec).as_dict()
    env = {**os.environ, "ORCH_MAX_HOPS": "5"}
    for arm in RERUN_ARMS[:1] + RERUN_ARMS[2:]:          # generic_composed, generic_planned
        rc = subprocess.run([sys.executable, __file__, "_arm", "--arm", arm, "--root", root,
                             "--workers", str(workers)], cwd=REPO, env=env).returncode
        guard = json.loads((Path(root) / arm / "socket_guard.json").read_text())
        print(f"{arm}: exit {rc}, model-port attempts {len(guard['attempts'])}")
        if rc:
            raise SystemExit(f"{arm} failed")
    t = time.time()
    effort = spec.reasoning_default or "medium"
    rc = subprocess.run([sys.executable, __file__, "_llm_arm", "--arm", "generic_planned_llm", "--root", root,
                         "--workers", str(workers)], cwd=REPO,
                        env={**env, "LLM_REASONING_EFFORT": effort}).returncode
    from utils.llm.registry import clear_identity_cache
    clear_identity_cache()
    after = require_identity(spec).as_dict()
    (Path(root) / "generic_planned_llm" / "identity.json").write_text(json.dumps(
        {"model": spec.name, "reasoning_effort": effort, "before": before, "after": after}, indent=1))
    print(f"generic_planned_llm: exit {rc}, {time.time() - t:.0f}s, identity before/after verified")
    if rc:
        raise SystemExit("generic_planned_llm failed")


def code_qwen(out: Path, root: Path) -> dict:
    """A-1: code the Qwen planner's lost questions with the same coder and rules."""
    authored, det = H.load_arm(root, H.AUTHORED), H.load_arm(root, H.DET)
    llm = H.load_arm(root, H.LLM)
    qs = H.lost(authored, llm)
    cs = [H.code(q, authored[q], llm[q], arm=H.LLM) for q in qs]
    rec = [H.recode_builder_walk(c, llm[c.qid]) for c in cs]
    st, st2 = Counter(c.stage for c in cs), Counter(c.stage for c in rec)
    cov = {a: H.coverage(x) for a, x in ((H.AUTHORED, authored), (H.DET, det), (H.LLM, llm))}
    gen = [d for d in llm.values()]
    res = {
        "root": str(root.relative_to(REPO) if root.is_relative_to(REPO) else root),
        "identity": json.loads((root / H.LLM / "identity.json").read_text()),
        "counts": {a: len(x) for a, x in ((H.AUTHORED, authored), (H.DET, det), (H.LLM, llm))},
        "coverage": {a: round(statistics.mean(c.values()), 4) for a, c in cov.items()},
        "llm_minus_authored": H.paired(cov[H.AUTHORED], cov[H.LLM]),
        "det_minus_authored": H.paired(cov[H.AUTHORED], cov[H.DET]),
        "llm_minus_det": H.paired(cov[H.DET], cov[H.LLM]),
        "llm_planner_used": dict(Counter((d.get("run_meta") or {}).get("planner") for d in gen)),
        "n_lost": len(qs),
        "causes": dict(Counter(c.cause for c in cs).most_common()),
        "stages": dict(st), "downstream_share": round(st["downstream"] / len(cs), 4) if cs else None,
        "mechanisms": dict(Counter(f"{c.cause}:{c.mechanism.split(':')[0]}" for c in cs).most_common()),
        "builder_walk": {"recoded": sum(a.cause != b.cause for a, b in zip(cs, rec)),
                         "causes": dict(Counter(c.cause for c in rec).most_common()), "stages": dict(st2),
                         "downstream_share": round(st2["downstream"] / len(rec), 4) if rec else None},
        "overlap_with_det_lost": len(set(qs) & set(H.lost(authored, det))),
        "det_lost_today": len(H.lost(authored, det)),
        "socket_guard_attempts": {a: len(json.loads((root / a / "socket_guard.json").read_text())["attempts"])
                                  for a in (H.AUTHORED, H.DET)},
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "attribution-qwen.json").write_text(json.dumps(res, indent=1))
    with open(out / "codings-qwen.jsonl", "w") as fh:
        for c in cs:
            fh.write(json.dumps(c.as_dict(), ensure_ascii=False) + "\n")
    return res


def _guarded_arm(arm: str, root: str, workers: int) -> int:
    rec = Path(root) / arm / "socket_guard.json"
    rec.parent.mkdir(parents=True, exist_ok=True)
    _install_guard(rec)
    from utils.evaluation import experiment_untruncated as exp

    return exp.main(["--arm", arm, "--root", root, "--bank", BANK, "--workers", str(workers)])


def rerun(root: str, workers: int) -> None:
    env = {**os.environ, "ORCH_MAX_HOPS": "5"}
    for arm in RERUN_ARMS:
        t = time.time()
        rc = subprocess.run([sys.executable, __file__, "_arm", "--arm", arm, "--root", root,
                             "--workers", str(workers)], cwd=REPO, env=env).returncode
        guard = json.loads((Path(root) / arm / "socket_guard.json").read_text())
        print(f"{arm}: exit {rc}, {time.time() - t:.0f}s, model-port attempts {len(guard['attempts'])}")
        if rc:
            raise SystemExit(f"{arm} failed")


# --------------------------------------------------------------------------- #
# code
# --------------------------------------------------------------------------- #


def code_all(out: Path, rerun_root: Path | None) -> dict:
    root = REPO / H.SAVED_ROOT
    authored, det, llm = H.load_arm(root, H.AUTHORED), H.load_arm(root, H.DET), H.load_arm(root, H.LLM)
    res: dict = {"saved_root": str(H.SAVED_ROOT)}
    codings = []
    for arm, planned in ((H.DET, det), (H.LLM, llm)):
        qs = H.lost(authored, planned)
        cs = [H.code(q, authored[q], planned[q], arm=arm) for q in qs]
        codings += cs
        causes = Counter(c.cause for c in cs)
        stages = Counter(c.stage for c in cs)
        mech = Counter(f"{c.cause}:{c.mechanism.split(':')[0]}" for c in cs)
        flags = Counter(f.split(":")[0] for c in cs for f in set(x.split(":")[0] for x in c.flags))
        tiers: dict[str, Counter] = defaultdict(Counter)
        for c in cs:
            tiers[H.tier_of(c.qid)][c.cause] += 1
        res[arm] = {
            "n_lost": len(qs), "one_cause_each": all(c.cause in H.CAUSES for c in cs) and len(cs) == len(qs),
            "causes": dict(causes.most_common()), "stages": dict(stages),
            "downstream_share": round(stages["downstream"] / len(cs), 4) if cs else None,
            "mechanisms": dict(mech.most_common()), "any_flag": dict(flags.most_common()),
            "by_tier": {t: dict(c) for t, c in sorted(tiers.items())},
        }
    # Post-hoc sensitivity: the builder's fixed walk counted as downstream (RESULTS §4).
    for arm, planned in ((H.DET, det), (H.LLM, llm)):
        cs = [c for c in codings if c.arm == arm]
        rec = [H.recode_builder_walk(c, planned[c.qid]) for c in cs]
        st = Counter(c.stage for c in rec)
        res[arm]["posthoc_builder_walk"] = {
            "recoded": sum(a.cause != b.cause for a, b in zip(cs, rec)),
            "causes": dict(Counter(c.cause for c in rec).most_common()), "stages": dict(st),
            "downstream_share": round(st["downstream"] / len(rec), 4) if rec else None}
    both = sorted(set(H.lost(authored, det)) & set(H.lost(authored, llm)))
    by = {(c.arm, c.qid): c for c in codings}
    res["both_lost"] = {"n": len(both),
                        "same_cause": sum(by[(H.DET, q)].cause == by[(H.LLM, q)].cause for q in both),
                        "pairs": dict(Counter(f"{by[(H.DET, q)].cause} | {by[(H.LLM, q)].cause}" for q in both).most_common())}
    res["saved_coverage"] = {a: round(statistics.mean(H.coverage(x).values()), 4)
                             for a, x in ((H.AUTHORED, authored), (H.DET, det), (H.LLM, llm))}
    res["saved_paired"] = {"det_minus_authored": H.paired(H.coverage(authored), H.coverage(det)),
                           "llm_minus_authored": H.paired(H.coverage(authored), H.coverage(llm)),
                           "llm_minus_det": H.paired(H.coverage(det), H.coverage(llm))}

    if rerun_root:
        runs = {a: H.load_arm(rerun_root, a) for a in RERUN_ARMS}
        cov = {a: H.coverage(x) for a, x in runs.items()}
        res["rerun"] = {
            "root": str(rerun_root.relative_to(REPO) if rerun_root.is_relative_to(REPO) else rerun_root),
            "counts": {a: len(x) for a, x in runs.items()},
            "coverage": {a: round(statistics.mean(c.values()), 4) for a, c in cov.items()},
            "limits_effect_capped_minus_composed": H.paired(cov["generic_composed"], cov["generic_composed_capped"]),
            "decomposition_effect_planned_minus_capped": H.paired(cov["generic_composed_capped"], cov["generic_planned"]),
            "plan_effect_planned_minus_composed": H.paired(cov["generic_composed"], cov["generic_planned"]),
            "drift_vs_saved": {
                "generic_composed": H.paired(H.coverage(authored), cov["generic_composed"]),
                "generic_planned": H.paired(H.coverage(det), cov["generic_planned"]),
            },
            "lost_today": len(H.lost(runs["generic_composed"], runs["generic_planned"])),
            "socket_guard_attempts": {a: len(json.loads((rerun_root / a / "socket_guard.json").read_text())["attempts"])
                                      for a in RERUN_ARMS},
        }
        # Post-hoc: the deterministic planner's losses on today's tree, coded the same way.
        today = [H.code(q, runs["generic_composed"][q], runs["generic_planned"][q], arm=H.DET)
                 for q in H.lost(runs["generic_composed"], runs["generic_planned"])]
        res["rerun"]["today_det_causes"] = dict(Counter(c.cause for c in today).most_common())
        res["rerun"]["today_det_overlap_with_saved_77"] = len({c.qid for c in today} & set(H.lost(authored, det)))
        timings = defaultdict(list)
        for d in runs["generic_planned"].values():
            t = (d.get("run_meta") or {}).get("timings") or {}
            if "plan_ms" in t:
                timings["plan_ms"].append(float(t["plan_ms"]))
            if "total_ms" in t:
                timings["total_ms"].append(float(t["total_ms"]))
            for sp in t.get("specialists") or []:
                ms = sp.get("ms") or sp.get("elapsed_ms") or sp.get("wall_ms") if isinstance(sp, dict) else None
                if ms is not None:
                    timings["specialist_ms"].append(float(ms))
        res["rerun"]["stage_timing_generic_planned"] = {
            k: {"n": len(v), "median": round(statistics.median(v), 1),
                "p95": round(sorted(v)[int(0.95 * (len(v) - 1))], 1)} for k, v in timings.items() if v}
    out.mkdir(parents=True, exist_ok=True)
    (out / "attribution.json").write_text(json.dumps(res, indent=1))
    with open(out / "codings.jsonl", "w") as fh:
        for c in codings:
            fh.write(json.dumps(c.as_dict(), ensure_ascii=False) + "\n")
    return res


# --------------------------------------------------------------------------- #
# packets and agreement
# --------------------------------------------------------------------------- #


def packets(out: Path) -> None:
    root = REPO / H.SAVED_ROOT
    authored = H.load_arm(root, H.AUTHORED)
    rng = random.Random(SEED)
    pdir = out / "packets"
    pdir.mkdir(parents=True, exist_ok=True)
    index = []
    for arm in (H.DET, H.LLM):
        planned = H.load_arm(root, arm)
        sample = rng.sample(H.lost(authored, planned), 20)
        for q in sample:
            name = f"{arm}__{q}".replace("/", "_").replace(":", "_")
            (pdir / f"{name}.json").write_text(json.dumps(H.packet(q, authored[q], planned[q], arm), indent=1))
            index.append({"file": f"packets/{name}.json", "arm": arm, "qid": q})
    (out / "packets_index.json").write_text(json.dumps(index, indent=1))
    print(f"{len(index)} packets in {pdir}")


def agree(out: Path) -> dict:
    auto = {(c["arm"], c["qid"]): c for c in map(json.loads, (out / "codings.jsonl").read_text().splitlines())}
    second = json.loads((out / "annotator2.json").read_text())
    rows = []
    for s in second:
        a = auto[(s["arm"], s["qid"])]
        rows.append({"arm": s["arm"], "qid": s["qid"], "auto": a["cause"], "annotator": s["cause"],
                     "auto_stage": a["stage"], "annotator_stage": H.STAGE.get(s["cause"], "?"),
                     "annotator_reason": s.get("reason", "")})
    res = {}
    for arm in (H.DET, H.LLM, "all"):
        rs = [r for r in rows if arm == "all" or r["arm"] == arm]
        res[arm] = {"n": len(rs),
                    "exact": round(sum(r["auto"] == r["annotator"] for r in rs) / len(rs), 4) if rs else None,
                    "kappa": H.cohen_kappa([r["auto"] for r in rs], [r["annotator"] for r in rs]),
                    "stage_agreement": round(sum(r["auto_stage"] == r["annotator_stage"] for r in rs) / len(rs), 4)
                    if rs else None}
    res["disagreements"] = [r for r in rows if r["auto"] != r["annotator"]]
    (out / "agreement.json").write_text(json.dumps(res, indent=1))
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rerun")
    r.add_argument("--root", required=True)
    r.add_argument("--workers", type=int, default=8)
    rq = sub.add_parser("rerun-qwen")
    rq.add_argument("--root", required=True)
    rq.add_argument("--workers", type=int, default=32)
    cq = sub.add_parser("code-qwen")
    cq.add_argument("--root", required=True)
    cq.add_argument("--out", required=True)
    la = sub.add_parser("_llm_arm")
    la.add_argument("--arm", required=True)
    la.add_argument("--root", required=True)
    la.add_argument("--workers", type=int, default=32)
    g = sub.add_parser("_arm")
    g.add_argument("--arm", required=True)
    g.add_argument("--root", required=True)
    g.add_argument("--workers", type=int, default=8)
    for name in ("code", "packets", "agree"):
        p = sub.add_parser(name)
        p.add_argument("--out", required=True)
        if name == "code":
            p.add_argument("--rerun-root", default=None)
    args = ap.parse_args(argv)
    if args.cmd == "rerun":
        rerun(args.root, args.workers)
    elif args.cmd == "rerun-qwen":
        rerun_qwen(args.root, args.workers)
    elif args.cmd == "code-qwen":
        print(json.dumps(code_qwen(Path(args.out), REPO / args.root), indent=1)[:5000])
    elif args.cmd == "_llm_arm":
        return _llm_arm(args.arm, args.root, args.workers)
    elif args.cmd == "_arm":
        return _guarded_arm(args.arm, args.root, args.workers)
    elif args.cmd == "code":
        res = code_all(Path(args.out), (REPO / args.rerun_root) if args.rerun_root else None)
        print(json.dumps({k: v for k, v in res.items()}, indent=1)[:6000])
    elif args.cmd == "packets":
        packets(Path(args.out))
    elif args.cmd == "agree":
        print(json.dumps(agree(Path(args.out)), indent=1)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
