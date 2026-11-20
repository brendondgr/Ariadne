"""Score the written-id smoke against EXP-2026-11-018, item by item."""
import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/bdgr/Agents/Ariadne")
from scripts.era2_catalog_score import confidently_wrong_variant, dev_outcome, dev_ids, dev_records, load_dev  # noqa: E402

S = Path(sys.argv[1])
R = Path("/home/bdgr/Agents/Ariadne/docs/evaluation/experiments/typed-engine-fixes-2026-11-20")
AUTH = Path("/home/bdgr/Agents/Ariadne/docs/evaluation/experiments")
sel = json.loads((S / "selection.json").read_text())
targets = {tuple(t) for t in sel["targets"]}


def fired(typed):
    return [f for t in typed or [] for f in t.get("coercions") or [] if f.get("filled_by") == "written_id"]


def var(arm):
    old = {(r["case_id"], r["tier"]): r for r in json.loads((R / "variants" / f"{arm}.json").read_text())}
    p = S / f"{arm}.json"
    if not p.exists():
        print(arm, "missing"); return
    new = [r for r in json.loads(p.read_text()) if "records_exact" in r]
    agg = {"target": [0, 0, 0, 0, 0, 0, 0], "control": [0, 0, 0, 0, 0, 0, 0]}
    print(f"== variants {arm}")
    for r in sorted(new, key=lambda r: (r["case_id"], r["tier"])):
        k = (r["case_id"], r["tier"]); o = old[k]; g = "target" if k in targets else "control"
        f = fired(r.get("typed"))
        a = agg[g]
        a[0] += 1; a[1] += bool(o["records_exact"]); a[2] += bool(r["records_exact"])
        a[3] += confidently_wrong_variant(o); a[4] += confidently_wrong_variant(r); a[5] += bool(f)
        a[6] += (not r.get("entity_ids"))
        print(f"  {g:7} {k[0]:14} {k[1]} exact {int(bool(o['records_exact']))}->{int(bool(r['records_exact']))} "
              f"CW {int(confidently_wrong_variant(o))}->{int(confidently_wrong_variant(r))} "
              f"guard={'+'.join(str(x['to']) for x in f) or '-'} ids={','.join(r.get('entity_ids') or [])[:80]}")
    for g, a in agg.items():
        print(f"  {g}: n={a[0]} exact {a[1]}->{a[2]} CW {a[3]}->{a[4]} guard fired {a[5]} empty {a[6]}")


def dev(label, old_dir, new_dir, authored_dir):
    if not new_dir.exists():
        print(label, "missing"); return
    new, old, auth = load_dev(new_dir / "answers"), load_dev(old_dir / "answers"), load_dev(authored_dir)
    print(f"== dev {label}")
    for i in sel_dev:
        n, o, a = new.get(i), old.get(i), auth.get(i)
        g = "target" if i in dev_sel["targets"] else "control"
        on, nn = dev_outcome(o, a), dev_outcome(n, a)
        f = fired((n or {}).get("run_meta", {}).get("typed"))
        same = n is not None and a is not None and dev_ids(n) == dev_ids(a)
        print(f"  {g:7} {i[:58]:58} lost {int(on['lost'])}->{int(nn['lost'])} CW {int(on['confidently_wrong'])}->"
              f"{int(nn['confidently_wrong'])} ids==authored {same} recs {dev_records(n) if n else None} "
              f"guard={'+'.join(str(x['to']) for x in f) or '-'}")


dev_sel = json.loads((S / "dev_selection.json").read_text())
sel_dev = dev_sel["targets"] + dev_sel["controls"]
for arm in ("T-lazy", "T-lazy-G"):
    var(arm)
AUTHORED = Path(sys.argv[2])
dev("qwen T-lazy", R / "dev/planned_llm_typed_lazy", S / "dev/planned_llm_typed_lazy", AUTHORED)
dev("qwen T-full", R / "dev/planned_llm_typed_full", S / "dev/planned_llm_typed_full", AUTHORED)
dev("gemma T-lazy", R / "dev-gemma/planned_llm_typed_lazy", S / "dev-gemma/planned_llm_typed_lazy", AUTHORED)
