"""Gold recall measured against the ANSWER TEXT, not against identifiers.

`deterministic_scores.coverage` matches gold items by id, so it cannot see a
gold item the catalogue publishes only as text — every CAPEC prerequisite,
consequence, execution step, example and indicator. This reads the same gold
assertions and asks whether the answer actually states them.

Two deliberate tolerances, both one-way:

* **Abstentions count.** An honest "the executed query returned nothing for
  CAPEC-659" names the entity the gold asks for, and it is part of the answer
  the judge reads.
* **A long gold string is matched by its WORDS, not byte-for-byte.** The gold
  composes an execution step as ``step phase description`` and a consequence as
  ``scopes impacts``; the graph stores those as separate properties in its own
  order. Demanding the catalogue's exact concatenation would measure phrasing
  rather than whether the answer says the thing. Short gold items —
  identifiers — still have to appear verbatim.

This is a PROXY for the judged score, not a substitute. It tracked the Step 6
judgments closely enough to steer repair work (D4 0.5381 here against 0.5405
judged, D5 0.9674 against 0.9160) while costing seconds instead of nine hours.
"""
import json, os, sys, collections

#: Below this length a gold item is an identifier and must appear verbatim.
VERBATIM_UNDER = 40
#: Fraction of a long gold item's words the answer must contain.
WORD_RECALL = 0.8


def norm(s):
    return " ".join(str(s).split()).lower()


def _words(s):
    return {w for w in "".join(c if c.isalnum() else " " for c in s).split() if len(w) > 2}


def states(answer_text, answer_words, item):
    item_n = norm(item)
    if len(item_n) < VERBATIM_UNDER:
        return item_n in answer_text
    if item_n[:180] in answer_text:
        return True
    want = _words(item_n)
    if not want:
        return False
    return len(want & answer_words) / len(want) >= WORD_RECALL


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
            + " " + " ".join(x.get("statement", "") for x in (ans.get("abstentions") or []))
        )
        words = _words(text)
        g = (a.get("gold") or {}).get("assertions") or {}
        want = list(g.get("must_include_ids") or []) + list(g.get("must_include_related") or [])
        if not want:
            continue
        rows[a["id"]] = sum(1 for w in want if states(text, words, w)) / len(want)
    return rows


def _roll(rows):
    byt = collections.defaultdict(list)
    for k, v in rows.items():
        byt[k.split("-")[0]].append(v)
    print(f"n={len(rows)}  gold-text recall {sum(rows.values())/len(rows):.4f}")
    for t in sorted(byt):
        v = byt[t]
        print(f"  {t} n={len(v):3d}  {sum(v)/len(v):.4f}")


if __name__ == "__main__":
    rows = score(sys.argv[1])
    _roll(rows)
    if len(sys.argv) > 2:
        other = score(sys.argv[2])
        keys = sorted(set(rows) & set(other))
        down = [(k, rows[k], other[k]) for k in keys if other[k] < rows[k] - 1e-9]
        up = [k for k in keys if other[k] > rows[k] + 1e-9]
        print(f"\nB: {sum(other[k] for k in keys)/len(keys):.4f}  "
              f"improved={len(up)} REGRESSED={len(down)}")
        for k, o, n in sorted(down, key=lambda r: r[2]-r[1])[:25]:
            print(f"  {o:.2f} -> {n:.2f}  {k}")
