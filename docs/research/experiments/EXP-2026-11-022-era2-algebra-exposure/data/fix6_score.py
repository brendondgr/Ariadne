"""Fix round 6 prove-small scorer (PROTOCOL Amendment 5). Run from the repo root."""
import json
import sys
from pathlib import Path

sys.path.insert(0, "scripts")
from era2_catalog_score import AUTHORED, dev_outcome, load_dev  # noqa: E402

G = Path("docs/evaluation/experiments/algebra-exposure-2026-11-20")
SMALL = G / "fix6-small"
FIX4 = G / "fix4-small"  # the arms exempt from the control clause
BASE = G / "fix5-small"  # the probe baseline and the item set (Amendment 5)
DA = {"T-lazy": "planned_llm_typed_lazy", "T-full": "planned_llm_typed_full", "T-lazy-G": "planned_llm_typed_lazy"}
DEVDIR = {"T-lazy": "dev/planned_llm_typed_lazy", "T-full": "dev/planned_llm_typed_full",
          "T-lazy-G": "dev-gemma/planned_llm_typed_lazy"}
ctrl_keys = {(v["case_id"], v["tier"], v["question"]) for v in json.load(open(G / "stage-round4/variants.json"))}
authored = load_dev(Path(AUTHORED))


def rows(p):
    return {(r["case_id"], r["tier"], r["question"]): r for r in json.load(open(p)) if "records_exact" in r}


def ops(r):
    return [s["step"].get("algebra") for s in ((r.get("planner") or {}).get("plan") or [])
            if (s.get("step") or {}).get("kind") == "algebra"]


def text_scan(r):
    return '"contains_text"' in json.dumps((r.get("planner") or {}).get("plan")) or \
        '"starts_with"' in json.dumps((r.get("planner") or {}).get("plan"))


out = {}
for cfg in ("core", "core+ext"):
    for arm in ("T-lazy", "T-full", "T-lazy-G"):
        d = SMALL / cfg / arm
        if not (d / f"{arm}.json").exists():
            continue
        new = rows(d / f"{arm}.json")
        off = rows(G / "phase-h/off-A/variants" / f"{arm}.json")
        old = rows(G / "phase-h/core-superseded-2/variants" / f"{arm}.json")
        b5 = BASE / cfg / arm / f"{arm}.json"
        base_rows = rows(b5) if b5.exists() else {}
        keys = [k for k in new if k not in ctrl_keys]
        was_lost = [k for k in keys if off.get(k, {}).get("records_exact") and not old.get(k, {}).get("records_exact")]
        rec = [k for k in was_lost if new[k]["records_exact"]]
        still_op = [k for k in keys if off.get(k, {}).get("records_exact") and not new[k]["records_exact"] and ops(new[k])]
        still_txt = [k for k in still_op if text_scan(new[k])]
        old_op = [k for k in was_lost if ops(old[k])]
        ctl_lost = [k for k in new if k in ctrl_keys and not new[k]["records_exact"]]
        ctl_lost_op = [f"{k[0]} {k[1]}" for k in ctl_lost if ops(new[k])]
        ctl_lost_op_offA_right = [f"{k[0]} {k[1]}" for k in ctl_lost if ops(new[k]) and off.get(k, {}).get("records_exact")]
        # dev controls
        dv = load_dev(d / "dev" / DA[arm] / "answers") if (d / "dev" / DA[arm] / "answers").exists() else {}
        dev_bad = [i for i, a in dv.items() if (o := dev_outcome(a, authored.get(i)))["lost"] or o["confidently_wrong"]]
        dev_bad_op = [i for i in dev_bad if any((s.get("step") or {}).get("kind") == "algebra"
                                               for s in ((dv[i].get("run_meta") or {}).get("observed_plan") or []))]
        offd = G / "phase-h/off-A" / DEVDIR[arm] / "answers"
        dv_off = load_dev(offd) if offd.exists() else {}
        dev_bad_op_offA_right = [i for i in dev_bad_op if i in dv_off and not (
            (o := dev_outcome(dv_off[i], authored.get(i)))["lost"] or o["confidently_wrong"])]
        # probe tune vs round 4
        ps = json.load(open(d / "probe-score.json"))["by_switch"] if (d / "probe-score.json").exists() else {}
        r4p = BASE / cfg / arm / "probe-score.json"
        r4 = json.load(open(r4p))["by_switch"] if r4p.exists() else {}
        # refusals of the new kind
        n_ref = sum(1 for r in new.values() for t in (r.get("typed") or []) for f in (t.get("refusals") or [])
                    if "matches the stored characters exactly" in json.dumps(f) and not f.get("final"))
        teach_final = [f"{k[0]} {k[1]}" for k, r in new.items() for t in (r.get("typed") or [])
                       for f in (t.get("refusals") or []) if f.get("final") and (
                           "matches the stored characters exactly" in f.get("detail", "")
                           or "looks up one named entity" in f.get("detail", ""))]
        lookups = sum(1 for r in new.values() for t in (r.get("typed") or []) for f in (t.get("coercions") or [])
                      if f.get("filled_by") == "lookup_scan_to_anchor")
        bp = FIX4 / cfg / arm / f"{arm}.json"
        base_new = rows(bp) if bp.exists() else {}
        base_ctl_op = [f"{k[0]} {k[1]}" for k in base_new if k in ctrl_keys and not base_new[k]["records_exact"]
                       and ops(base_new[k])]
        out[f"{cfg}/{arm}"] = {
            "core_lost_items": len(was_lost), "recovered": len(rec),
            "operator_losses_vs_offA_now": len(still_op), "of_which_text_scan": len(still_txt),
            "operator_losses_vs_offA_in_core_sitting_2": len(old_op),
            "recovered_in_fix5": len([k for k in was_lost if base_rows.get(k, {}).get("records_exact")]),
            "variant_controls_lost": len(ctl_lost), "variant_controls_lost_with_operator": ctl_lost_op,
            "dev_controls_bad": len(dev_bad), "dev_controls_bad_with_operator": dev_bad_op,
            "probe_tune_now": {g: v["exact"] for g, v in ps.items()},
            "probe_tune_fix5": {g: v["exact"] for g, v in r4.items()},
            "empty_text_scan_refusals": n_ref,
            "teaching_refusals_final": teach_final,
            "lookup_scan_to_anchor": lookups,
            "fix4_controls_lost_with_operator": base_ctl_op,
            "controls_lost_with_operator_offA_right": ctl_lost_op_offA_right + dev_bad_op_offA_right,
            "join_key_labels": sum(1 for r in new.values() for t in (r.get("typed") or []) for f in (t.get("coercions") or [])
                                   if f.get("filled_by") == "join_key_labels"),
            "producer_labels": sum(1 for r in new.values() for t in (r.get("typed") or []) for f in (t.get("coercions") or [])
                                   if f.get("filled_by") == "producer_labels"),
        }
for k, v in out.items():
    print(k, json.dumps(v))
json.dump(out, open(SMALL / "score.json", "w"), indent=1)
