"""Treatments that change how a closed decision is put to a fast model (EXP-2026-11-014).

Each treatment derives new items from Step 7's items (EXP-2026-11-013), so the
control is Step 7's run records on the same items:

- **wording:** each relation option is shown as a plain reading written once per
  card relation (``readings.json``), in place of the arrow and the shared gloss;
- **yes/no:** one binary question per real option; "none" when nothing passes;
- **rule filter:** options whose target type the question does not name are dropped;
- **verifier:** a binary check of a pick another model already made;
- **shortlist:** the menu cut to the options a model's probabilities keep, then
  shown to the controller.
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from utils.decision.items import NONE, REPO, Item

READING_MAX_WORDS = 12


# --------------------------------------------------------------------------- #
# Relation keys and readings
# --------------------------------------------------------------------------- #

def item_label(item: Item) -> str:
    """The known entity's label, from a D4 item's context ``... <id> (<Label>)...``."""
    m = re.search(r"\(([A-Za-z]+)\)", item.context)
    assert m, item.id
    return m.group(1)


def reading_key(dataset: str, label: str, option_key: str) -> str:
    return f"{dataset}|{label}|{option_key}"


def relation_keys(items: list[Item]) -> list[str]:
    out = set()
    for it in items:
        if it.decision != "D4":
            continue
        for k in it.options:
            if k != NONE:
                out.add(reading_key(it.tags["dataset"], item_label(it), k))
    return sorted(out)


def readings_brief(keys: list[str]) -> str:
    """The writer's whole input: the cards' node and relation descriptions and the keys.

    The cards' ``relationship_paraphrases`` are left out on purpose: the question
    generator drew on them, so they would carry question wording into the options.
    """
    lines = [
        "# Brief: plain readings for graph relations",
        "",
        "You are writing one short reading for each relation below. A reading tells a person which",
        "related things they get if they follow that relation from a known entity.",
        "",
        "Each key is `dataset|Label|RELATION|direction|TargetLabel`:",
        "- `out` means Label -RELATION-> TargetLabel; `in` means TargetLabel -RELATION-> Label.",
        "- The known entity is always the `Label`. The reading names what you reach: the `TargetLabel` things.",
        "",
        "Rules for each reading:",
        "1. A noun phrase from the known entity's point of view, for example \"the sub-techniques this",
        "   software uses\" or \"the groups that use this software\".",
        f"2. At most {READING_MAX_WORDS} words. Plain English: no CamelCase or ALL_CAPS schema names, no arrows.",
        "3. Get the direction right: `in` and `out` of the same relation read differently.",
        "4. Every reading for the same dataset and Label must differ from the others, so a reader can",
        "   tell any two apart.",
        "5. Use the descriptions below for meaning. Do not invent facts beyond them.",
        "",
        "Return one JSON object mapping every key to its reading, and nothing else.",
        "",
    ]
    for ds in ("attack", "capec"):
        card = json.loads((REPO / "data/source_cards" / f"{ds}.json").read_text())
        ed = card.get("entity_descriptions") or {}
        lines += [f"## Dataset `{ds}`", "", "### Node types", ""]
        lines += [f"- `{k}`: {v}" for k, v in sorted((ed.get("nodes") or {}).items())]
        lines += ["", "### Relations", ""]
        lines += [f"- `{k}`: {v}" for k, v in sorted((ed.get("relationships") or {}).items())]
        lines += ["", "### Keys to write", ""]
        lines += [f"- `{k}`" for k in keys if k.startswith(ds + "|")]
        lines.append("")
    return "\n".join(lines)


_SCHEMA_WORD = re.compile(r"\b(?:[A-Z][a-z]+[A-Z][A-Za-z]*|[A-Z]{2,}_[A-Z_]+|[A-Z]{3,})\b|->|<-")


def check_readings(readings: dict[str, str], keys: list[str]) -> list[str]:
    """Problems with a readings file; an empty list means it passes."""
    problems = []
    missing = sorted(set(keys) - set(readings))
    extra = sorted(set(readings) - set(keys))
    problems += [f"missing: {k}" for k in missing] + [f"unknown key: {k}" for k in extra]
    by_label: dict[str, dict[str, str]] = {}
    for k, v in readings.items():
        if k not in keys:
            continue
        v = str(v).strip()
        if not v:
            problems.append(f"empty: {k}")
            continue
        if len(v.split()) > READING_MAX_WORDS:
            problems.append(f"over {READING_MAX_WORDS} words: {k}: {v}")
        if _SCHEMA_WORD.search(v):
            problems.append(f"schema name or arrow: {k}: {v}")
        ds, label = k.split("|")[:2]
        seen = by_label.setdefault(f"{ds}|{label}", {})
        norm = " ".join(v.lower().split())
        if norm in seen:
            problems.append(f"same reading as {seen[norm]}: {k}: {v}")
        seen[norm] = k
    return problems


# --------------------------------------------------------------------------- #
# Treatment item builders
# --------------------------------------------------------------------------- #

def wording_item(item: Item, readings: dict[str, str]) -> Item:
    ds, label = item.tags["dataset"], item_label(item)
    opts = {k: (v if k == NONE else readings[reading_key(ds, label, k)]) for k, v in item.options.items()}
    return replace(item, id="W:" + item.id, options=opts)


def _label_words(label: str) -> list[str]:
    w = re.sub(r"(?<!^)(?=[A-Z])", " ", label).lower()
    return sorted({w, w.replace(" ", "-"), w.replace(" ", "")})


def named_targets(item: Item) -> list[str]:
    """The real options whose target type the question names (plural allowed)."""
    q = item.question.lower()
    out = []
    for k in item.options:
        if k == NONE:
            continue
        target = k.split("|")[2]
        if any(re.search(r"\b" + re.escape(w) + r"(?:e?s)?\b", q) for w in _label_words(target)):
            out.append(k)
    return out


def rulefilter_item(item: Item) -> Item | None:
    """The item narrowed to the named target types, or None when the rule leaves it unchanged."""
    real = [k for k in item.options if k != NONE]
    named = named_targets(item)
    if not named or len(named) == len(real):
        return None
    opts = {k: v for k, v in item.options.items() if k in named or k == NONE}
    return replace(item, id="R:" + item.id, options=opts,
                   tags={**item.tags, "rulefilter_kept": len(named), "rulefilter_from": len(real)})


def yesno_prompt(item: Item, key: str) -> str:
    text = item.option_text(key)
    if item.decision == "D4":
        return f"Following this relation from the known entity: {text}. Does it answer the question?"
    label = re.search(r"Which (\w+) does", item.prompt)
    return f"Does the question refer to this {label.group(1) if label else 'entry'}: {text}?"


def yesno_binary(item: Item, key: str) -> Item:
    """One option's yes/no question as a binary item (for clients that take one question per call)."""
    return Item(id=f"{item.id}#{key}", decision=item.decision, group=item.group, stratum=item.stratum,
                context=item.context, question=item.question, prompt=yesno_prompt(item, key),
                options={"yes": "yes", "no": "no"}, gold="yes" if key == item.gold else "no",
                tags={"parent": item.id, "option": key})


def verifier_item(item: Item, pick: str) -> Item:
    return Item(id="V:" + item.id, decision=item.decision, group=item.group, stratum=item.stratum,
                context=item.context, question=item.question,
                prompt=f"Proposed answer: {item.option_text(pick)}. Is it the right one?",
                options={"yes": "yes", "no": "no"}, gold="yes" if pick == item.gold else "no",
                tags={"parent": item.id, "pick": pick})


def shortlist_keys(probs: dict[str, float], q: float) -> list[str]:
    """Real options by probability until their summed probability reaches ``q``."""
    real = sorted(((k, v) for k, v in probs.items() if k != NONE), key=lambda kv: (-kv[1], kv[0]))
    total = sum(v for _, v in real) or 1.0
    kept, acc = [], 0.0
    for k, v in real:
        kept.append(k)
        acc += v / total
        if acc >= q:
            break
    return kept


def shortlist_item(item: Item, keep: list[str], first_order: list[str]) -> Item:
    """The item with only ``keep`` and "none", in the item's first option order (no leak of the ranking)."""
    order = [k for k in first_order if k in keep or k == NONE]
    opts = {k: item.options[k] for k in order}
    return replace(item, id="S:" + item.id, options=opts, tags={**item.tags, "shortlist": len(keep)})


def load_readings(path: Path) -> dict[str, str]:
    return json.loads(path.read_text())


__all__ = ["check_readings", "item_label", "load_readings", "named_targets", "reading_key", "readings_brief",
           "relation_keys", "rulefilter_item", "shortlist_item", "shortlist_keys", "verifier_item",
           "wording_item", "yesno_binary", "yesno_prompt"]


# --------------------------------------------------------------------------- #
# Yes/no, batched: all of an item's option questions in one request
# --------------------------------------------------------------------------- #

def yesno_batch(server: str, item: Item, order: list[str], *, yes_first: bool,
                base: str | None = None) -> tuple[dict[str, float], float]:
    """P(yes) for every real option of ``item``, asked in one request.

    ``order`` fixes the question order; ``yes_first`` the order of the two answers.
    Returns ({option key: P(yes)}, milliseconds).
    """
    import time

    from utils.decision.clients import _post

    keys = [k for k in order if k != NONE]
    state = item.context.strip() + "\n\nQuestion: " + item.question.strip()
    ans = ["yes", "no"] if yes_first else ["no", "yes"]
    t = time.time()
    if server == "pplx":
        url = (base or "http://127.0.0.1:7500").rstrip("/") + "/v1/decisions"
        qs = {f"q{i}": {"type": "choice", "question": yesno_prompt(item, k),
                        "criteria": {f"c{j + 1}": a for j, a in enumerate(ans)}} for i, k in enumerate(keys)}
        r = _post(url, {"state": state, "temperature": 1.0, "questions": qs})
        out = {}
        for i, k in enumerate(keys):
            p = r["answers"][f"q{i}"]["probabilities"]
            out[k] = float(p.get(f"c{ans.index('yes') + 1}", 0.0))
    elif server == "d3":
        url = (base or "http://127.0.0.1:5107").rstrip("/") + "/v1/decide"
        labels = [f"{'AB'[j]}) {a}" for j, a in enumerate(ans)]
        qs = [{"id": f"q{i}", "type": "choice", "question": yesno_prompt(item, k), "options": labels}
              for i, k in enumerate(keys)]
        r = _post(url, {"input": state, "questions": qs})
        yes_label = labels[ans.index("yes")]
        out = {k: float(r["answers"][f"q{i}"]["probs"].get(yes_label, 0.0)) for i, k in enumerate(keys)}
    else:
        raise ValueError(server)
    return out, (time.time() - t) * 1000


def yesno_decide(s: dict[str, float], theta: float) -> tuple[str, float]:
    """The pick and its confidence from P(yes) per option: "none" when nothing reaches ``theta``."""
    if not s:
        return NONE, 0.0
    k = max(s, key=lambda x: (s[x], x))
    return (k, s[k]) if s[k] >= theta else (NONE, 1.0 - s[k])
