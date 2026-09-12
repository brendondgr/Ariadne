"""Gold recall measured against the ANSWER TEXT, not against identifiers.

`deterministic_scores.coverage` matches gold items by id, so it cannot see a
gold item the catalogue publishes only as text — every CAPEC prerequisite,
consequence, execution step, example and indicator. This reads the same gold
assertions and asks whether the answer actually states them.
"""
import json, os, sys, collections

def norm(s):
    return " ".join(str(s).split()).lower()

def score(d):
    rows = {}
    for f in os.listdir(d):
        if ".judgment." in f:
            continue
        a = json.load(open(os.path.join(d, f)))
        ans = a.get("answer") or {}
        text = norm(
            (ans.get("headline") or "") + " " + (ans.get("narrative") or "")
            + " " + " ".join(c.get("text", "") for c in (ans.get("claims") or []))
        )
        g = (a.get("gold") or {}).get("assertions") or {}
        want = list(g.get("must_include_ids") or []) + list(g.get("must_include_related") or [])
        if not want:
            continue
        hit = sum(1 for w in want if norm(w)[:180] in text)
        rows[a["id"]] = hit / len(want)
    return rows

rows = score(sys.argv[1])
byt = collections.defaultdict(list)
for k, v in rows.items():
    byt[k.split("-")[0]].append(v)
print(f"n={len(rows)}  gold-text recall {sum(rows.values())/len(rows):.4f}")
for t in sorted(byt):
    v = byt[t]
    print(f"  {t} n={len(v):3d}  {sum(v)/len(v):.4f}")
if len(sys.argv) > 2:
    other = score(sys.argv[2])
    keys = sorted(set(rows) & set(other))
    down = [(k, rows[k], other[k]) for k in keys if other[k] < rows[k] - 1e-9]
    up = [k for k in keys if other[k] > rows[k] + 1e-9]
    print(f"\nB: {sum(other[k] for k in keys)/len(keys):.4f}  improved={len(up)} REGRESSED={len(down)}")
    for k, o, n in sorted(down, key=lambda r: r[2]-r[1])[:25]:
        print(f"  {o:.2f} -> {n:.2f}  {k}")
