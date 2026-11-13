"""Card-generated grounding questions: the right anchor is known by construction.

Entities are drawn from the labels real questions anchor on, spread across
degree tertiles within each label, and never from an anchor any bank has used.
Each entity is written at four tiers that mirror the real banks' tiers:

- ``id``           — "What is T1047?"            (real T1/T2)
- ``name``         — the exact name               (real T3)
- ``paraphrase``   — the name re-said conceptually without its words, by the
                      model on :9090              (real T4)
- ``description``  — a one-line reference built from the node's description,
                      by the model on :9090       (real T5)

A leak check rejects a paraphrase or description containing the id, an alias,
or any rare (document frequency <= 1%) token of the name; a rejected item is
regenerated once with the leaked words named, then dropped and counted.
"""

from __future__ import annotations

import json
import math
import random
import re
from collections import defaultdict
from functools import lru_cache

from utils.specialists.schema.namesearch import index_for

from .. import banks, candidates
from ..config import REPO
from ..relay import RelayClient
from ..t2 import interpretations as I

TIERS = ("id", "name", "paraphrase", "description")
LABELS = ("AttackPattern", "Technique", "Software", "Campaign", "SubTechnique", "Group",
          "Tactic", "Mitigation", "DataComponent", "Category")
_WORD = re.compile(r"[a-z0-9]+")

DESCRIBE_FRAMES = (
    "What is {ref}?",
    "Tell me about {ref}.",
    "Can you give me the details on {ref}?",
    "Summarise what the catalogue says about {ref}.",
    "What do we know about {ref}?",
    "Give me an overview of {ref}.",
)
RELATION_FRAMES = (
    "Which {target} entities are linked to {ref} ({words})?",
    "List the {target} entries connected to {ref} by {words}.",
    "For {ref}, what are the related {target} entries ({words})?",
    "Show me every {target} associated with {ref} through {words}.",
    "What {target} records does the catalogue tie to {ref} via {words}?",
    "I need the {target} items that relate to {ref} ({words}).",
)


@lru_cache(maxsize=None)
def aliases(dataset: str) -> dict[str, tuple[str, ...]]:
    """entity id -> aliases, from the canonical snapshot (ATT&CK groups/software carry them)."""
    out: dict[str, tuple[str, ...]] = {}
    path = REPO / "data" / "graphs" / dataset / "canonical" / "nodes.jsonl"
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        node = json.loads(line)
        props = node.get("properties") or {}
        eid = str(props.get("attack_id") or node.get("id") or "")
        m = re.match(r"^capec:[a-z-]+:(\d+)$", eid, re.IGNORECASE)
        eid = f"CAPEC-{m.group(1)}" if m else eid
        al = props.get("aliases") or props.get("x_mitre_aliases") or []
        if isinstance(al, str):
            try:
                al = json.loads(al)
            except json.JSONDecodeError:
                al = [al]
        name = str(node.get("name") or "")
        out[eid] = tuple(a for a in al if isinstance(a, str) and a and a != name)
    return out


def excluded_anchors() -> set[str]:
    out = {i.gold_anchor for i in banks.all_items() if i.gold_anchor}
    data = json.loads((REPO / "utils/specialists/evalset/drawn_anchors.json").read_text())
    for b in (data.get("banks") or {}).values():
        out.update(b.get("anchors") or [])
    return out


def degrees(gx) -> dict[str, int]:
    """Total degree of every candidate entity, from the live stores."""
    out: dict[str, int] = {}
    rows = gx._cypher().run(
        "MATCH (n) WHERE n.attack_id IS NOT NULL RETURN n.attack_id AS id, COUNT { (n)--() } AS d",
        {}, {"max_result_rows": 1_000_000, "query_timeout_ms": 120_000})
    out.update({str(r["id"]): int(r["d"]) for r in rows})
    from utils.specialists.gremlin.normalizer import _expand_member_id
    rows = gx._gremlin().run(
        'g.V().hasLabel("AttackPattern","Category","View").project("id","d")'
        '.by(values("id")).by(bothE().count())',
        {}, {"max_result_rows": 1_000_000, "query_timeout_ms": 120_000})
    out.update({_expand_member_id(str(r["id"])): int(r["d"]) for r in rows})
    return out


def sample_entities(n: int, seed: int, deg: dict[str, int]) -> list[candidates.Entity]:
    rng = random.Random(seed)
    excl = excluded_anchors()
    pool: dict[str, list[candidates.Entity]] = defaultdict(list)
    for ds in candidates.DATASETS:
        for e in candidates.entities(ds).values():
            if e.label in LABELS and e.entity_id not in excl and e.name:
                pool[e.label].append(e)
    # allocation proportional to sqrt(label population), at least 10 (or all)
    weights = {l: math.sqrt(len(v)) for l, v in pool.items()}
    tot = sum(weights.values())
    alloc = {l: min(len(pool[l]), max(10, round(n * w / tot))) for l, w in weights.items()}
    chosen: list[candidates.Entity] = []
    for label in sorted(pool):
        ents = sorted(pool[label], key=lambda e: (deg.get(e.entity_id, 0), e.entity_id))
        k = alloc[label]
        thirds = [ents[i * len(ents) // 3:(i + 1) * len(ents) // 3] for i in range(3)]
        per = [k // 3 + (1 if i < k % 3 else 0) for i in range(3)]
        for t, m in zip(thirds, per):
            chosen.extend(rng.sample(t, min(m, len(t))))
    rng.shuffle(chosen)
    return chosen


def _rare_name_tokens(e: candidates.Entity) -> set[str]:
    ix = index_for(e.dataset)
    return {w for w in _WORD.findall(e.name.lower()) if len(w) >= 3 and ix.token_df(w) <= 0.01}


def leaks(text: str, e: candidates.Entity) -> list[str]:
    low = (text or "").lower()
    toks = set(_WORD.findall(low))
    bad = [w for w in _rare_name_tokens(e) if w in toks]
    if e.entity_id.lower() in low:
        bad.append(e.entity_id)
    if e.name.lower() in low:
        bad.append(e.name)
    for a in aliases(e.dataset).get(e.entity_id, ()):
        if len(a) >= 3 and re.search(r"\b" + re.escape(a.lower()) + r"\b", low):
            bad.append(a)
    return bad


_PARA = ("You rename things without naming them. Given a cybersecurity catalogue entry, write a "
         "short noun phrase (at most 15 words) that someone might use to refer to it WITHOUT using "
         "its name, any word from its name, any alias, or its identifier. Re-say the name's meaning "
         "conceptually. Reply with the phrase only.")
_DESC = ("You describe things without naming them. Given a cybersecurity catalogue entry, write a "
         "one-line reference (at most 30 words) built only from what its description says it is or "
         "does, WITHOUT using its name, any word from its name, any alias, or its identifier. Reply "
         "with the reference only, as a noun phrase.")


def _clean(text: str) -> str:
    t = (text or "").strip().strip('"').strip()
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.S).strip()
    return t.splitlines()[0].strip().rstrip(".") if t else ""


def reword(relay: RelayClient, alias: str, e: candidates.Entity, tier: str) -> dict:
    system = _PARA if tier == "paraphrase" else _DESC
    al = ", ".join(aliases(e.dataset).get(e.entity_id, ())[:8])
    user = (f"Entry type: {e.label}\nName: {e.name}\nIdentifier: {e.entity_id}\n"
            + (f"Aliases: {al}\n" if al else "")
            + f"Description: {' '.join(e.description.split())[:1200]}")
    attempts = []
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    for _ in range(2):
        c = relay.complete(alias, msgs, temperature=0.7)
        text = _clean(c.text)
        bad = leaks(text, e) if text else ["<empty>"]
        attempts.append({"text": text, "leaks": bad, "served_model": c.served_model})
        if not bad:
            return {"text": text, "ok": True, "attempts": attempts}
        msgs = msgs + [{"role": "assistant", "content": c.text},
                       {"role": "user", "content": f"That uses forbidden words: {', '.join(bad)}. Rewrite without them."}]
    return {"text": None, "ok": False, "attempts": attempts}


def frame(rng: random.Random, e: candidates.Entity, ref: str) -> str:
    facets = [f for f in I.facets_for(e.dataset, e.label) if f != "describe"]
    if facets and rng.random() < 0.5:
        rel, _d, target = facets[rng.randrange(len(facets))].split("|")
        words = " ".join(I._split(rel)) or rel
        return rng.choice(RELATION_FRAMES).format(ref=ref, target=target, words=words)
    return rng.choice(DESCRIBE_FRAMES).format(ref=ref)
