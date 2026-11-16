#!/usr/bin/env python3
"""EXP-2026-11-010: MiniCPM 4.7 35B against Qwen 3.8 27B on the kill tests' part A (CypherBench).

    uv run python scripts/minicpm_vs_qwen.py replay               # Qwen's saved replies, re-executed today
    uv run python scripts/minicpm_vs_qwen.py run --condition on   # MiniCPM, thinking on (primary)
    uv run python scripts/minicpm_vs_qwen.py run --condition off  # MiniCPM, reasoning_effort=none
    uv run python scripts/minicpm_vs_qwen.py compare --out <experiment>/data

Each run writes to its own folder under ``logs/killtests-2026-11/``. MiniCPM's
run header is written from the registry's verified identity: the kill-test
runner identifies models by end-of-turn id, and 248046 would label MiniCPM as
``qwen38-27b``.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

BASE = REPO / "logs" / "killtests-2026-11"
QWEN_SRC = BASE / "exp006"
OUT = {"replay": BASE / "exp010-replay-qwen", "on": BASE / "exp010-minicpm-on", "off": BASE / "exp010-minicpm-off",
       "on_recovered": BASE / "exp010-minicpm-on-recovered", "qwen_today": BASE / "exp010-qwen-today"}
TAG = {"replay": "qwen38-27b", "on": "minicpm47-35b", "off": "minicpm47-35b"}
PRIMARY = ("typed3-3shot-cypher", "free-cypher-3shot")
ARMS = ("free-cypher-3shot", "free-gremlin-3shot", "typed2-3shot-cypher", "typed2-3shot-gremlin",
        "typed3-3shot-cypher", "typed3-3shot-gremlin", "typed3-3shot-repair-cypher", "typed3-3shot-repair-gremlin")


CONCURRENCY = int(os.environ.get("EXP010_CONCURRENCY", "32"))


def _runner(out: Path, extra_env: dict[str, str]) -> None:
    env = {**os.environ, "KILLTESTS_EXPERIMENT": "exp006", "KILLTESTS_EXP005_OUT": str(out),
           "KILLTESTS_CONCURRENCY": str(CONCURRENCY), **extra_env}
    t = time.time()
    rc = subprocess.run([sys.executable, "-m", "utils.killtests.t2c.run", "A"], cwd=REPO, env=env).returncode
    print(f"runner exit {rc} in {time.time() - t:.0f}s")
    if rc:
        raise SystemExit(rc)


def replay() -> None:
    out = OUT["replay"]
    if out.exists():
        raise SystemExit(f"{out} exists; remove it to replay again")
    (out / "cache").mkdir(parents=True)
    hdr = json.loads((QWEN_SRC / "run_header.json").read_text())
    hdr["identities"] = [i for i in hdr["identities"] if i["model"] == "qwen38-27b"]
    hdr["replay_of"] = "EXP-2026-11-006 part A (saved generations and repairs, re-executed on today's tree)"
    (out / "run_header.json").write_text(json.dumps(hdr, indent=1))
    for stage in ("A-generate", "A-repair"):
        for suffix in (".json", ".done"):
            shutil.copy2(QWEN_SRC / f"{stage}{suffix}", out / f"{stage}{suffix}")
        shutil.copy2(QWEN_SRC / "cache" / f"{stage}.jsonl", out / "cache" / f"{stage}.jsonl")
    # keep only Qwen's rows in the copied stages, so scoring sees one model
    for stage in ("A-generate", "A-repair"):
        d = json.loads((out / f"{stage}.json").read_text())
        key = "generations" if "generations" in d else next(k for k in d if isinstance(d[k], dict))
        d[key] = {k: v for k, v in d[key].items() if k.endswith("|qwen38-27b")}
        if "models" in d:
            d["models"] = {a: t for a, t in d["models"].items() if t == "qwen38-27b"}
        (out / f"{stage}.json").write_text(json.dumps(d))
    _runner(out, {})


def run(condition: str) -> None:
    from utils.llm.registry import load, require_identity

    out = OUT[condition]
    out.mkdir(parents=True, exist_ok=True)
    hp = out / "run_header.json"
    if not hp.exists():
        spec = load().default
        if spec.name != "minicpm47-35b":
            raise SystemExit(f"registry default is {spec.name}, not minicpm47-35b")
        ident = require_identity(spec)
        hdr = {"started_at": time.time(),
               "identities": [{"alias": spec.alias, "model": spec.name, "envelope_model": ident.envelope_model,
                               "last_token_id": ident.last_token_id, "verified_by": "utils.llm.registry (token id + prompt fingerprint)"}],
               "concurrency_per_model": 32, "max_tokens": 8192,
               "reasoning_effort": {spec.name: "none"} if condition == "off" else {}}
        hp.write_text(json.dumps(hdr, indent=1))
    extra = {"KILLTESTS_REASONING_EFFORT": json.dumps({"minicpm47-35b": "none"})} if condition == "off" else {}
    _runner(out, extra)


def recover() -> None:
    """POST-HOC (RESULTS §4): re-request the thinking-on replies the server misfiled.

    A reply whose text arrived only as reasoning is re-requested with thinking on
    and token ids. If the think block was never closed (no 248069) and the model
    stopped on its own, the reasoning text is the answer and becomes ``raw``. The
    rest of the pipeline (repair, execute, score) then runs unchanged in a new
    folder. Temperature 0, so the re-request should reproduce the same reply.
    """
    import concurrent.futures as cf
    import urllib.request

    os.environ["KILLTESTS_EXPERIMENT"] = "exp006"
    from utils.killtests.t2c.run import Bench

    src, out = OUT["on"], OUT["on_recovered"]
    if out.exists():
        raise SystemExit(f"{out} exists; remove it to recover again")
    (out / "cache").mkdir(parents=True)
    shutil.copy2(src / "run_header.json", out / "run_header.json")
    gen = json.loads((src / "A-generate.json").read_text())
    b = Bench("A")
    qs = {q["qid"]: q for q in b.gold}
    todo = [k for k, v in gen["generations"].items() if not (v.get("raw") or "").strip() and (v.get("reasoning_chars") or 0) > 0]

    def one(k):
        qid, arm, _tag = k.split("|")
        body = {"model": "default-model", "temperature": 0.0, "max_tokens": 8192, "return_token_ids": True,
                "messages": b.messages(arm, qs[qid])}
        req = urllib.request.Request("http://localhost:9090/v1/chat/completions", data=json.dumps(body).encode(),
                                     headers={"content-type": "application/json"})
        d = json.load(urllib.request.urlopen(req, timeout=900))
        c = d["choices"][0]
        m, ids = c["message"], c.get("token_ids") or []
        unclosed = c.get("finish_reason") == "stop" and 248069 not in ids and not (m.get("content") or "").strip()
        text = (m.get("reasoning") or "") if unclosed else (m.get("content") or "")
        return k, {"text": text, "unclosed": unclosed, "same_length": len(m.get("reasoning") or "") == gen["generations"][k]["reasoning_chars"]}

    with cf.ThreadPoolExecutor(32) as ex:
        got = dict(ex.map(one, todo))
    for k, g in got.items():
        gen["generations"][k] = {**gen["generations"][k], "raw": g["text"][-6000:], "recovered_from_reasoning": g["unclosed"]}
    gen["recovery"] = {"rerequested": len(todo), "unclosed": sum(g["unclosed"] for g in got.values()),
                       "same_reasoning_length": sum(g["same_length"] for g in got.values())}
    (out / "A-generate.json").write_text(json.dumps(gen))
    (out / "A-generate.done").write_text("")
    with open(out / "cache" / "A-generate.jsonl", "w") as fh:
        for k, v in gen["generations"].items():
            fh.write(json.dumps({"key": k, "value": v}) + "\n")
    print("recovery:", gen["recovery"])
    _runner(out, {})


def qwen_today() -> None:
    """Amendment A-1: part A on today's Qwen 3.8 27B, at reasoning_effort=medium."""
    from utils.llm.registry import load, require_identity

    out = OUT["qwen_today"]
    out.mkdir(parents=True, exist_ok=True)
    hp = out / "run_header.json"
    if not hp.exists():
        spec = load()["qwen38-27b"]
        ident = require_identity(spec)
        hp.write_text(json.dumps({
            "started_at": time.time(),
            "identities": [{"alias": spec.alias, "model": spec.name, "envelope_model": ident.envelope_model,
                            "last_token_id": ident.last_token_id,
                            "verified_by": "utils.llm.registry (token id + default-rendering fingerprint)"}],
            "concurrency_per_model": CONCURRENCY, "max_tokens": 8192,
            "reasoning_effort": {spec.name: "medium"}}, indent=1))
    _runner(out, {"KILLTESTS_REASONING_EFFORT": json.dumps({"qwen38-27b": "medium"})})


# --------------------------------------------------------------------------- #
# compare
# --------------------------------------------------------------------------- #


def vectors(folder: Path, tag: str) -> dict[str, list[int]]:
    gold = json.loads((BASE / "t1" / "gold.json").read_text())["questions"]
    ex = json.loads((folder / "A-execute.json").read_text())["executions"]
    vec = {}
    for arm in ("cypher-3shot", "gremlin-3shot", "typed2-3shot", "typed3-3shot", "typed3-3shot-repair"):
        outs = [ex.get(f"{q['qid']}|{arm}|{tag}") or {} for q in gold]
        if arm.startswith("typed"):
            vec[f"{arm}-cypher"] = [int(bool(o.get("cypher_ok"))) for o in outs]
            vec[f"{arm}-gremlin"] = [int(bool(o.get("gremlin_ok"))) for o in outs]
        else:
            vec[f"free-{arm}"] = [int(bool(o.get("correct"))) for o in outs]
    return vec


def gen_stats(folder: Path, tag: str) -> dict:
    gens = json.loads((folder / "A-generate.json").read_text())["generations"]
    rows = [v for k, v in gens.items() if k.endswith(f"|{tag}")]
    lat = sorted(float(v.get("latency_s") or 0) for v in rows)
    toks = sorted(int((v.get("usage") or {}).get("completion_tokens") or 0) for v in rows)
    return {"n": len(rows),
            "reasoning_only": sum(1 for v in rows if not (v.get("raw") or "").strip() and (v.get("reasoning_chars") or 0) > 0),
            "empty": sum(1 for v in rows if not (v.get("raw") or "").strip()),
            "cut_off": sum(1 for v in rows if v.get("finish_reason") == "length"),
            "latency_median_s": lat[len(lat) // 2] if lat else None,
            "completion_tokens_median": toks[len(toks) // 2] if toks else None}


def compare(out: Path) -> dict:
    from utils.killtests.t1.run import _paired_ci

    saved = json.loads((QWEN_SRC / "A-score.json").read_text())["by_model"]["qwen38-27b"]["arms"]
    q_saved = {a: round(saved[a]["exact_records"], 4) for a in ARMS}
    q_replay = vectors(OUT["replay"], "qwen38-27b")
    res: dict = {"qwen_saved": q_saved,
                 "qwen_replay": {a: round(sum(v) / len(v), 4) for a, v in q_replay.items()}}
    res["replay_reproduces"] = all(abs(res["qwen_replay"][a] - q_saved[a]) <= 0.005 for a in PRIMARY)
    ref = q_replay
    for cond in ("on", "off", "on_recovered"):
        if not (OUT[cond] / "A-execute.json").exists():
            continue
        m = vectors(OUT[cond], "minicpm47-35b")
        rng = random.Random(20261115)
        block = {"exact_records": {a: round(sum(v) / len(v), 4) for a, v in m.items()},
                 "minus_qwen": {}, "generation": gen_stats(OUT[cond], "minicpm47-35b")}
        for a in m:
            d = (sum(m[a]) - sum(ref[a])) / len(ref[a])
            block["minus_qwen"][a] = {"diff": round(d, 4), "ci95": [round(x, 4) for x in _paired_ci(ref[a], m[a], rng)]}
        rep = json.loads((OUT[cond] / "A-repair.json").read_text())
        block["repairs"] = rep.get("n_repaired", len(rep.get("generations") or {}))
        verdicts = []
        for a in PRIMARY:
            d, (lo, hi) = block["minus_qwen"][a]["diff"], block["minus_qwen"][a]["ci95"]
            verdicts.append("worse" if d < -0.05 and hi < 0 else "same_or_better" if d >= -0.05 else "inconclusive")
        block["decision"] = ("ask for Qwen back" if "worse" in verdicts else
                             "stay on MiniCPM" if all(v == "same_or_better" for v in verdicts) else "inconclusive")
        block["primary_verdicts"] = dict(zip(PRIMARY, verdicts))
        res[f"minicpm_{cond}"] = block
    res["qwen_generation"] = gen_stats(QWEN_SRC, "qwen38-27b")
    if (OUT["qwen_today"] / "A-execute.json").exists():
        t = vectors(OUT["qwen_today"], "qwen38-27b")
        rng = random.Random(20261116)
        res["qwen_today"] = {
            "exact_records": {a: round(sum(v) / len(v), 4) for a, v in t.items()},
            "minus_saved_qwen": {a: {"diff": round((sum(t[a]) - sum(ref[a])) / len(ref[a]), 4),
                                     "ci95": [round(x, 4) for x in _paired_ci(ref[a], t[a], rng)]} for a in t},
            "generation": gen_stats(OUT["qwen_today"], "qwen38-27b"),
        }
        res["qwen_today"]["same_behaviour"] = all(abs(res["qwen_today"]["minus_saved_qwen"][a]["diff"]) <= 0.03
                                                  for a in PRIMARY)
    out.mkdir(parents=True, exist_ok=True)
    (out / "comparison.json").write_text(json.dumps(res, indent=1))
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("replay")
    sub.add_parser("recover")
    sub.add_parser("qwen-today")
    r = sub.add_parser("run")
    r.add_argument("--condition", choices=("on", "off"), required=True)
    c = sub.add_parser("compare")
    c.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "replay":
        replay()
    elif a.cmd == "recover":
        recover()
    elif a.cmd == "qwen-today":
        qwen_today()
    elif a.cmd == "run":
        run(a.condition)
    else:
        print(json.dumps(compare(Path(a.out)), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
