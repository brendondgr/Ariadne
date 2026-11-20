"""Before/after diff of the store fix: ids must match; bytes reported."""
import json, sys, glob, os, collections
S = sys.argv[1]; B, A = f"{S}/before", f"{S}/after"
CLOCK = {"wall_s", "timing_ms", "elapsed_ms", "duration_ms", "latency_ms", "timings", "built_at", "started_at", "finished_at", "created_at"}
def strip(x):
    if isinstance(x, dict): return {k: strip(v) for k, v in x.items() if k not in CLOCK}
    if isinstance(x, list): return [strip(v) for v in x]
    return x
def ids_of(ans):
    out = set()
    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("entity_ids", "ids", "identifiers") and isinstance(v, list): out.update(map(str, v))
                else: walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
    walk(ans); return out
report = {}
# R reference
rb = {r["case_id"]: r for r in json.load(open(f"{B}/variants/reference.json"))}
ra = {r["case_id"]: r for r in json.load(open(f"{A}/variants/reference.json"))}
report["R"] = {"n": len(rb), "ids_same": sum(rb[k].get("entity_ids") == ra.get(k, {}).get("entity_ids") for k in rb),
               "bytes_same": sum(strip(rb[k]) == strip(ra.get(k)) for k in rb),
               "ids_diff": [k for k in rb if rb[k].get("entity_ids") != ra.get(k, {}).get("entity_ids")][:20],
               "bytes_diff": [k for k in rb if strip(rb[k]) != strip(ra.get(k))][:40]}
# deterministic banks
for b in ("bank-2026-08-19", "bank-2026-08-20", "dev"):
    fb = sorted(glob.glob(f"{B}/{b}/deterministic/answers/*.json")); n = len(fb); same_ids = same_bytes = 0; dids = []; dbytes = []
    for f in fb:
        g = f.replace("/before/", "/after/")
        x, y = json.load(open(f)), json.load(open(g)) if os.path.exists(g) else None
        if y is not None and ids_of(x) == ids_of(y): same_ids += 1
        else: dids.append(os.path.basename(f))
        if y is not None and strip(x) == strip(y): same_bytes += 1
        else: dbytes.append(os.path.basename(f))
    report[b] = {"n": n, "ids_same": same_ids, "bytes_same": same_bytes, "ids_diff": dids[:20], "bytes_diff": dbytes[:40]}
# replays
for a in ("T-lazy", "T-full", "T-lazy-G"):
    xb = {tuple(r["key"]): r for r in json.load(open(f"{B}/replay-{a}.json"))}
    xa = {tuple(r["key"]): r for r in json.load(open(f"{A}/replay-{a}.json"))}
    diff = [k for k in xb if xb[k].get("entity_ids") != xa.get(k, {}).get("entity_ids") or ("error" in xb[k]) != ("error" in xa.get(k, {}))]
    report[f"replay-{a}"] = {"n": len(xb), "ids_same": len(xb) - len(diff), "ids_diff": [list(k[:2]) for k in diff][:20]}
print(json.dumps(report, indent=1))
