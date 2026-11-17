#!/usr/bin/env python3
"""Questions with gold answers, generated from a source card alone (Era 2, Step 6).

Everything a question is *about* comes from the card: its labels, its
relationship glosses and paraphrases, and the schema facets derived from it
(which relationship joins which labels, in which direction). The graph is used
only to pick anchors and to execute each question's own typed request, so the
gold answer is known **by construction**.

Tiers (how the question refers to things), for answerable questions:

* ``identifier``          the anchor's public id ("CAPEC-66")
* ``name``                its exact name
* ``reworded_name``       its name re-said without its words
* ``description``         a reference built only from its description
* ``synonym_relation``    the relation said in words that are neither in its
                          name nor among the card's paraphrases for it
* ``paraphrased_schema``  the target label named by meaning, not by its name

Kinds (what the right exit is):

* ``answerable``       gold = the exact set;
* ``ambiguous``        two or more card-valid readings with different answers,
                       plus the gold clarification answer (for Step 12);
* ``out_of_coverage``  needs an operator the retrieval catalog lacks (for
                       ``not_expressible``);
* ``insufficient``     well formed and card-valid, but the graph holds no answer.

Anchors are split into tuning and held-out by a hash of the anchor id, so the
two splits never share an anchor; questions touching anchors from both splits
are dropped. Anchors used by any existing bank are excluded.

Rewordings are written by a language model (injectable: ``writer``) and
checked automatically for leaks; a leaking question is retried once with the
leaked words named, then dropped and counted.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

TIERS = ("identifier", "name", "reworded_name", "description", "synonym_relation", "paraphrased_schema")
KINDS = ("answerable", "ambiguous", "out_of_coverage", "insufficient")
#: Which decision step each question serves (Step 7's decisions, Step 12's clarification).
DECISION_OF_TIER = {"identifier": "grounding", "name": "grounding", "reworded_name": "grounding",
                    "description": "grounding", "synonym_relation": "relation_choice",
                    "paraphrased_schema": "relation_choice"}
DECISION_OF_KIND = {"ambiguous": "exit", "out_of_coverage": "exit", "insufficient": "exit"}
#: Operators assumed absent from the retrieval catalog (plan v2 Step 9 scopes it to retrieval).
MISSING_OPERATORS = ("path_search", "temporal_trend", "statistical_median", "similarity")
STOP = {"has", "have", "the", "of", "to", "in", "on", "by", "a", "an", "is", "are", "be", "can", "and",
        "or", "for", "with", "as", "at", "from", "its", "it", "this", "that", "into", "x", "mitre", "refs"}
_WORD = re.compile(r"[a-z0-9]+")
_SPLIT = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")

Writer = Callable[[str, str], str]          # (system, user) -> reply text


# --------------------------------------------------------------------------- #
# Card-derived pieces
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Slot:
    """One relation ask the schema allows: a ``label`` anchor, ``rel`` in ``direction``, to ``target``."""

    dataset: str
    label: str
    rel: str
    direction: str
    target: str

    def key(self) -> str:
        return f"{self.dataset}|{self.label}|{self.rel}|{self.direction}|{self.target}"


def words_of(name: str) -> list[str]:
    """``HAS_MITIGATION`` -> [has, mitigation]; ``CanFollow`` -> [can, follow]."""
    return [w.lower() for w in _SPLIT.findall(name.replace("_", " "))]


def stem(w: str) -> str:
    from utils.planner.lexicon import stem as _stem

    return _stem(w)


def forbidden_relation_stems(card: dict, rel: str) -> set[str]:
    """Stems of the relation's own words and of the card's paraphrases for it (minus stop words)."""
    words = set(words_of(rel))
    for phrase in (card.get("entity_descriptions") or {}).get("relationship_paraphrases", {}).get(rel, []) or []:
        words |= set(_WORD.findall(str(phrase).lower()))
    return {stem(w) for w in words if w not in STOP and len(w) >= 3}


def forbidden_label_stems(label: str) -> set[str]:
    """Stems of the label's words, plus its joined form ("SubTechnique" -> "subtechnique")."""
    words = words_of(label)
    out = {stem(w) for w in words if w not in STOP and len(w) >= 3}
    if len(words) >= 2:
        out.add(stem("".join(words)))
    return out


def plain_label(label: str) -> str:
    """How a person writes a schema label: ``DetectionStrategy`` -> ``detection strategy``,
    ``SubTechnique`` -> ``sub-technique``."""
    w = words_of(label)
    if len(w) >= 2 and w[0] == "sub":
        w = [f"sub-{w[1]}", *w[2:]]
    return " ".join(w)


_UNCOUNTED = {"software"}


def plural(phrase: str) -> str:
    """English plural of a plain label's last word (``taxonomy entry`` -> ``taxonomy entries``)."""
    head, _, last = phrase.rpartition(" ")
    if last in _UNCOUNTED:
        out = last
    elif last.endswith("ix"):
        out = last[:-2] + "ices"
    elif last.endswith("y") and last[-2:-1] not in set("aeiou"):
        out = last[:-1] + "ies"
    elif last.endswith(("s", "sh", "ch", "x")):
        out = last + "es"
    else:
        out = last + "s"
    return f"{head} {out}".strip()


def plain_template_text(card: dict, text: str) -> str:
    """Template questions in plain words: ``AttackPattern entries`` -> ``attack patterns``,
    ``per Group`` -> ``per group`` (EXP-2026-11-012 amendment 7)."""
    for label in sorted(card.get("node_labels") or [], key=len, reverse=True):
        text = re.sub(rf"\b{re.escape(label)} entries\b", plural(plain_label(label)), text)
        text = re.sub(rf"\b{re.escape(label)}\b", plain_label(label), text)
    return text


def schema_label_copied(label: str, text: str) -> list[str]:
    """A compound label written verbatim as one word ("Which SubTechnique entries ..."): a person
    would not type it, and it hands the agent the schema name (EXP-2026-11-012 amendment 6)."""
    if len(words_of(label)) < 2:
        return []
    return [f"schema label '{label}' written as one word"] if re.search(rf"\b{re.escape(label)}s?\b", text or "", re.I) else []


def leaked_stems(text: str, forbidden: set[str]) -> list[str]:
    toks = _WORD.findall((text or "").lower())
    return sorted({t for t in toks if stem(t) in forbidden})


#: Id-format and version hints copied from a label's description ("T-ID.NNN", "DET-IDs", "v19"):
#: they name the label by its id scheme, so the schema tier forbids them (EXP-2026-11-012 found 12).
_FORMAT_HINT = re.compile(r"\b[A-Z]{1,6}-IDs?\b|\bN{3,}\b|\bv\d+\b")


def format_hints(text: str) -> list[str]:
    return sorted(set(_FORMAT_HINT.findall(text or "")))


def relation_gloss(card: dict, rel: str) -> str:
    return str(((card.get("entity_descriptions") or {}).get("relationships") or {}).get(rel) or rel)


def label_gloss(card: dict, label: str) -> str:
    return str(((card.get("entity_descriptions") or {}).get("nodes") or {}).get(label) or label)


def card_slots(card: dict, registry: Any) -> list[Slot]:
    ds = card["dataset"]
    out = []
    for label in card.get("node_labels") or []:
        for f in registry.label_facets(label, dataset=ds) or []:
            out.append(Slot(ds, label, f.rel_type, f.direction, f.neighbour_label))
    return sorted(set(out), key=Slot.key)


def is_public_id(i: str) -> bool:
    """Ids a person would type: no composite ``a:b:c`` ids, no STIX uuids."""
    return bool(i) and ":" not in i and "--" not in i and len(i) <= 24


def split_of(dataset: str, anchor: str) -> str:
    h = int(hashlib.sha256(f"{dataset}|{anchor}".encode()).hexdigest(), 16)
    return "tuning" if h % 2 == 0 else "heldout"


# --------------------------------------------------------------------------- #
# Writing the questions
# --------------------------------------------------------------------------- #

SYS_QUESTION = ("You write one natural question a cybersecurity analyst might ask a knowledge graph. "
                "Follow the constraints exactly. Reply with the question only, on one line.")


def _direction_sentence(card: dict, slot: Slot) -> str:
    g = relation_gloss(card, slot.rel)
    side = "the source" if slot.direction == "out" else "the target"
    return (f"Relation {slot.rel}: {g} In this question the known entity (a {slot.label}) is {side} of the "
            f"relation, and the question asks for the {slot.target} entries on the other side.")


def question_rules(card: dict, slot: Slot, ref: str, tier: str) -> list[str]:
    """The writer's constraints for one question (shared by every writer, model or agent)."""
    rel_forbidden = forbidden_relation_stems(card, slot.rel)
    lab_forbidden = forbidden_label_stems(slot.target)
    rules = [f"Refer to the known entity exactly as: {ref}", _direction_sentence(card, slot)]
    plain = (f" Write kinds as an analyst would type them, in plain lower-case words ('{plain_label(slot.target)}')"
             + (f", never as the one-word label '{slot.target}'" if len(words_of(slot.target)) >= 2 else "")
             + ", and do not add the word 'entries' after a kind's name.")
    if tier == "synonym_relation":
        rules.append("Say the relation in your own everyday words. Do NOT use any of these words or any "
                     f"form of them: {', '.join(sorted(rel_forbidden))}.")
        clash = sorted({w for w in words_of(slot.target) if stem(w) in rel_forbidden})
        if clash:   # the kind's own name uses a forbidden word: it must be described instead
            rules.append(f"Name the asked-for kind ({slot.target}) in other plain words: its usual name uses "
                         f"the forbidden {', '.join(clash)}.{plain}")
        else:
            rules.append(f"You may name the asked-for kind as '{plain_label(slot.target)}'.{plain}")
    elif tier == "paraphrased_schema":
        rules.append(f"Name the asked-for kind ({slot.target}: {label_gloss(card, slot.target)}) by what it "
                     f"means, NOT by the words {', '.join(sorted(lab_forbidden))} or any form of them.")
        rules.append("Do not copy identifier formats or version tags from that description (such as "
                     "'X-ID', 'NNN' or 'v19').")
    else:
        rules.append(f"You may use the relation's own words and name the asked-for kind directly.{plain}")
    return rules


def question_problems(card: dict, slot: Slot, ref: str, tier: str, text: str, *,
                      name_forbidden: list[str] = ()) -> list[str]:
    """Why ``text`` breaks the rules for its tier (empty list: it passes)."""
    problems: list[str] = []
    if not text:
        return ["empty"]
    if ref.lower() not in text.lower():
        problems.append(f"missing the exact reference '{ref}'")
    if tier == "synonym_relation":
        problems += leaked_stems(text, forbidden_relation_stems(card, slot.rel))
    if tier == "paraphrased_schema":
        problems += leaked_stems(text, forbidden_label_stems(slot.target))
        problems += format_hints(text)
    problems += [w for w in name_forbidden if w.lower() in text.lower().replace(ref.lower(), "")]
    if tier != "paraphrased_schema":
        problems += schema_label_copied(slot.target, text.replace(ref, ""))
    return problems


def write_question(writer: Writer, card: dict, slot: Slot, ref: str, tier: str, *,
                   name_forbidden: list[str] = ()) -> dict[str, Any]:
    """One question for ``slot`` about the anchor referred to as ``ref``, at ``tier``. Leak-checked."""
    user = "\n".join(f"- {r}" for r in question_rules(card, slot, ref, tier))
    attempts = []
    msgs_user = user
    for _ in range(2):
        text = _one_line(writer(SYS_QUESTION, msgs_user))
        problems = question_problems(card, slot, ref, tier, text, name_forbidden=name_forbidden)
        attempts.append({"text": text, "problems": problems})
        if text and not problems:
            return {"text": text, "ok": True, "attempts": attempts}
        msgs_user = user + f"\n- Your last attempt broke the rules ({'; '.join(problems) or 'empty'}). Rewrite."
    return {"text": None, "ok": False, "attempts": attempts}


SYS_REWORD = ("You rename things without naming them. Given a cybersecurity catalogue entry, write a short noun "
              "phrase (at most 15 words) that refers to it WITHOUT using its name, any word from its name, any "
              "alias, or its identifier. Re-say the name's meaning conceptually. Reply with the phrase only.")
SYS_DESCRIBE = ("You describe things without naming them. Given a cybersecurity catalogue entry, write a "
                "one-line reference (at most 25 words) built only from what its description says it is or "
                "does, WITHOUT using its name, any word from its name, any alias, or its identifier. Reply "
                "with the reference only, as a noun phrase.")


def reference_entry(node: dict, label: str) -> str:
    """What a reference writer sees about the entry."""
    return (f"Entry type: {label}\nName: {node.get('name')}\nIdentifier: {node.get('id')}\n"
            f"Description: {' '.join(str(node.get('description') or '').split())[:1200]}")


def reference_problems(text: str, forbidden: list[str]) -> list[str]:
    return [w for w in forbidden if w and w.lower() in (text or "").lower()]


def write_reference(writer: Writer, node: dict, label: str, tier: str, forbidden: list[str]) -> dict[str, Any]:
    system = SYS_REWORD if tier == "reworded_name" else SYS_DESCRIBE
    user = reference_entry(node, label)
    attempts = []
    for _ in range(2):
        text = _one_line(writer(system, user)).rstrip(".")
        bad = reference_problems(text, forbidden)
        attempts.append({"text": text, "leaks": bad})
        if text and not bad:
            return {"text": text, "ok": True, "attempts": attempts}
        user += f"\nThat used forbidden words: {', '.join(bad) or 'empty'}. Rewrite without them."
    return {"text": None, "ok": False, "attempts": attempts}


def _one_line(text: str) -> str:
    t = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip().strip('"').strip()
    return t.splitlines()[0].strip() if t else ""


def name_forbidden_words(node: dict, rare: Callable[[str], bool]) -> list[str]:
    """The id, the full name, and every rare word of the name: none may appear in a reworded reference."""
    name = str(node.get("name") or "")
    words = [w for w in _WORD.findall(name.lower()) if len(w) >= 3 and rare(w)]
    return [str(node.get("id") or ""), name, *words]


# --------------------------------------------------------------------------- #
# The generator
# --------------------------------------------------------------------------- #


@dataclass
class GenConfig:
    seed: int = 20261116
    anchors_per_slot: int = 2
    ambiguous: int = 16
    out_of_coverage: int = 12
    insufficient: int = 24
    exclude: frozenset[str] = frozenset()
    workers: int = 32


@dataclass
class Generated:
    questions: list[dict[str, Any]] = field(default_factory=list)
    dropped: Counter = field(default_factory=Counter)
    notes: list[str] = field(default_factory=list)
    absent_slots: list[str] = field(default_factory=list)


def _bank_entry(dataset: str, qid: str, text: str, slot: Slot | None, anchor: str | None,
                gold: list[str], *, kind: str, tier: str, split: str, extra: dict[str, Any]) -> dict[str, Any]:
    entities = [slot.label, slot.rel, slot.target] if slot else []
    task = {"sub_question_id": qid, "source": dataset, "text": text, "entities": entities,
            "limits": {"max_traversal_depth": 3, "max_result_rows": 20000, "query_timeout_ms": 5000},
            "join_key": None, "seed_ids": [anchor] if anchor else [], "rationale": "card_generator"}
    return {
        "id": qid, "tier": tier, "split": split, "question": text, "task": task,
        "assertions": {"min_records": 1 if (kind == "answerable" and gold) else 0,
                       "must_include_ids": [anchor] if (anchor and kind == "answerable") else [],
                       "must_include_related": sorted(gold)},
        "ex_gold": {"pool": "neighbors", "expected": sorted(gold), "scheme": dataset},
        "card_gen": {"kind": kind, "tier": tier, "slot": asdict(slot) if slot else None, "anchor": anchor,
                     "gold_ids": sorted(gold), "decision": DECISION_OF_KIND.get(kind) or DECISION_OF_TIER.get(tier),
                     **extra},
    }


def generate(card: dict, registry: Any, backend: Any, writer: Writer, cfg: GenConfig, *,
             rare: Callable[[str], bool] = lambda w: True,
             public: Callable[[str], str] = lambda i: i) -> Generated:
    """All questions for one card. ``backend`` is a :mod:`utils.agent.exact` backend for its graph.

    ``public`` maps a stored id to the id a person writes (CAPEC stores
    ``capec:attack-pattern:66`` and publishes ``CAPEC-66``). Questions, gold and
    splits use public ids; fetches use stored ids, kept as ``anchor_storage``.
    """
    from concurrent.futures import ThreadPoolExecutor

    from utils.agent.exact import SetSpec, fetch
    from utils.agent.view import diagnose_empty

    ds = card["dataset"]
    rng = random.Random(f"{cfg.seed}|{ds}")
    out = Generated()
    slots = card_slots(card, registry)
    node_cache: dict[str, dict[str, dict]] = {}

    def nodes(label: str) -> dict[str, dict]:
        if label not in node_cache:
            node_cache[label] = {str(n["id"]): n for n in backend.nodes(label)}
        return node_cache[label]

    def gold(slot: Slot, anchor: str) -> list[str]:
        s = fetch(backend, SetSpec((anchor,), slot.rel, slot.direction, slot.target, slot.label))
        if not s.complete:
            raise RuntimeError(f"gold for {slot.key()} {anchor} hit the ceiling")
        return sorted(public(i) for i in s.ids)

    # ---- pick anchors per slot (and zero-degree anchors for `insufficient`) ----
    jobs: list[tuple[Slot, str]] = []
    empties: list[tuple[Slot, str]] = []
    for slot in slots:
        pool = {i: n for i, n in nodes(slot.label).items()
                if is_public_id(public(i)) and public(i) not in cfg.exclude}
        if not pool:
            continue
        deg = backend.degrees(slot.label, slot.rel, slot.direction, slot.target)
        if not any(deg.values()):
            # The card allows it, but no node of this label has a single such edge in the
            # store: a card/store mismatch (e.g. a relation name the store spells
            # differently), not a source of `insufficient` questions. Reported, never used.
            out.absent_slots.append(slot.key())
            continue
        live = sorted((i for i in pool if deg.get(i, 0) > 0), key=lambda i: (deg[i], i))
        if live:
            halves = [live[: max(1, len(live) // 2)], live[len(live) // 2:] or live]
            for k in range(min(cfg.anchors_per_slot, len(live))):
                jobs.append((slot, rng.choice(halves[k % 2])))
        zero = sorted(i for i in pool if deg.get(i, 0) == 0)
        if zero:
            empties.append((slot, rng.choice(zero)))

    # ---- anchor references (reworded name, description) ----
    anchors = sorted({(s.label, a) for s, a in jobs})

    def refs_for(item: tuple[str, str]) -> tuple[tuple[str, str], dict[str, Any]]:
        label, a = item
        node = nodes(label)[a]
        forb = name_forbidden_words({**node, "id": public(a)}, rare) + ([a] if a != public(a) else [])
        r = {"identifier": {"text": public(a), "ok": True},
             "name": {"text": str(node.get("name") or ""), "ok": bool(node.get("name"))}}
        r["reworded_name"] = write_reference(writer, node, label, "reworded_name", forb) if node.get("name") \
            else {"text": None, "ok": False}
        r["description"] = write_reference(writer, node, label, "description", forb) if node.get("description") \
            else {"text": None, "ok": False}
        r["_forbidden"] = forb
        return item, r

    with ThreadPoolExecutor(cfg.workers) as ex:
        refs = dict(ex.map(refs_for, anchors))

    # ---- answerable questions, every tier ----
    def one(job: tuple[Slot, str, str]) -> dict[str, Any] | None:
        slot, a, tier = job
        r = refs[(slot.label, a)]
        base = "identifier" if tier in ("synonym_relation", "paraphrased_schema") else tier
        ref = r[base]
        if not ref.get("ok"):
            return {"_dropped": f"{tier}: no {base} reference"}
        forb = r["_forbidden"] if base in ("reworded_name", "description") else []
        w = write_question(writer, card, slot, ref["text"], tier, name_forbidden=forb)
        if not w["ok"]:
            return {"_dropped": f"{tier}: leak or missing reference after retry"}
        return {"text": w["text"], "slot": slot, "anchor": a, "tier": tier, "attempts": len(w["attempts"])}

    tier_jobs = [(s, a, t) for s, a in jobs for t in TIERS]
    with ThreadPoolExecutor(cfg.workers) as ex:
        written = list(ex.map(one, tier_jobs))
    gold_cache: dict[tuple[str, str], list[str]] = {}
    for w in written:
        if w is None or "_dropped" in w:
            out.dropped[(w or {}).get("_dropped", "none")] += 1
            continue
        slot, a = w["slot"], w["anchor"]
        key = (slot.key(), a)
        if key not in gold_cache:
            gold_cache[key] = gold(slot, a)
        qid = "CG-" + hashlib.sha1(f"{slot.key()}|{a}|{w['tier']}".encode()).hexdigest()[:12]
        out.questions.append(_bank_entry(ds, qid, w["text"], slot, public(a), gold_cache[key], kind="answerable",
                                         tier=w["tier"], split=split_of(ds, public(a)),
                                         extra={"attempts": w["attempts"], "anchor_storage": a}))

    # ---- insufficient: card-valid ask, nothing in the graph ----
    rng.shuffle(empties)
    for slot, a in empties[: cfg.insufficient]:
        w = write_question(writer, card, slot, public(a), "identifier")
        if not w["ok"]:
            out.dropped["insufficient: leak or missing reference"] += 1
            continue
        diag = diagnose_empty(SetSpec((a,), slot.rel, slot.direction, slot.target, slot.label), backend)
        qid = "CG-" + hashlib.sha1(f"insufficient|{slot.key()}|{a}".encode()).hexdigest()[:12]
        out.questions.append(_bank_entry(ds, qid, w["text"], slot, public(a), [], kind="insufficient",
                                         tier="identifier", split=split_of(ds, public(a)),
                                         extra={"gold_status": "insufficient", "diagnosis": diag.get("reason"),
                                                "anchor_storage": a}))

    # ---- ambiguous (b): a neutral verb, two card relations to the same target ----
    # Runs first, with half the budget spread over the label pairs that allow it; the
    # entity kind below fills whatever is left. (EXP-2026-11-012's first runs split the
    # budget in fixed halves and wrote one question per pair: ATT&CK's card has no such
    # pair, CAPEC has one, so 8 and 1 of 16 were made.)
    amb = 0
    pairs: dict[tuple[str, str], list[Slot]] = defaultdict(list)
    for s in slots:
        pairs[(s.label, s.target)].append(s)
    eligible = [(k, g) for k, g in sorted(pairs.items())
                if len(g) >= 2 and any(sl.label == k[0] for sl, _ in jobs)]
    rel_budget = cfg.ambiguous // 2
    per_pair = -(-rel_budget // len(eligible)) if eligible else 0
    for (label, target), group in eligible:
        order = sorted({a for sl, a in jobs if sl.label == label})
        rng.shuffle(order)
        made = 0
        for a in order:
            if made >= per_pair or amb >= rel_budget:
                break
            readings = {sl.key(): gold(sl, a) for sl in group}
            if len({tuple(v) for v in readings.values()}) < 2 or not any(readings.values()):
                continue
            intended = rng.choice([sl for sl in group if readings[sl.key()]])
            pa = public(a)
            text = plain_template_text(card, rng.choice([f"Which {target} entries are connected to {pa}?",
                                                         f"What {target} entries does the graph link with {pa}?",
                                                         f"Show me the {target} entries associated with {pa}."]))
            qid = "CG-" + hashlib.sha1(f"amb-rel|{label}|{target}|{a}".encode()).hexdigest()[:12]
            out.questions.append(_bank_entry(
                ds, qid, text, intended, pa, readings[intended.key()], kind="ambiguous", tier="identifier",
                split=split_of(ds, pa),
                extra={"ambiguity": "relation", "readings": readings, "anchor_storage": a,
                       "clarification": {"question": plain_template_text(
                           card, f"Which link between {pa} and {target} entries do you mean?"),
                                         "options": [{"label": f"{sl.rel} ({sl.direction})",
                                                      "detail": relation_gloss(card, sl.rel)} for sl in group],
                                         "answer": f"{intended.rel} ({intended.direction})"}}))
            made += 1
            amb += 1
        if not made:
            out.dropped["ambiguous: no anchor separates the readings"] += 1

    # ---- ambiguous (a): two anchors share a name, answers differ (the rest of the budget) ----
    by_name: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for label in sorted({s.label for s in slots}):
        for i, n in nodes(label).items():
            # Names under 4 characters ("at") make ambiguous questions that read badly; skipped.
            if is_public_id(public(i)) and public(i) not in cfg.exclude and len(str(n.get("name") or "").strip()) >= 4:
                by_name[str(n["name"]).strip().lower()].append((label, i))
    for name, cands in sorted(by_name.items()):
        if amb >= cfg.ambiguous:
            break
        cands = sorted(set(cands))
        if len(cands) < 2 or len({split_of(ds, public(i)) for _, i in cands}) != 1:
            continue
        label0 = cands[0][0]
        slot = next((s for s in slots if s.label == label0), None)
        if slot is None:
            continue
        readings = {}
        for lab, i in cands:
            s2 = next((s for s in slots if s.label == lab and s.rel == slot.rel and s.target == slot.target), None)
            readings[public(i)] = gold(s2, i) if s2 else []
        if len({tuple(v) for v in readings.values()}) < 2:
            continue
        intended_sto = rng.choice([i for _, i in cands])
        intended = public(intended_sto)
        shown = str(nodes(label0)[cands[0][1]].get("name"))
        w = write_question(writer, card, slot, shown, "name")
        if not w["ok"]:
            out.dropped["ambiguous: leak or missing reference"] += 1
            continue
        qid = "CG-" + hashlib.sha1(f"amb-name|{name}|{slot.key()}".encode()).hexdigest()[:12]
        out.questions.append(_bank_entry(
            ds, qid, w["text"], slot, intended, readings[intended], kind="ambiguous", tier="name",
            split=split_of(ds, intended),
            extra={"ambiguity": "entity", "readings": dict(readings), "anchor_storage": intended_sto,
                   "readings_storage": {public(i): {"storage": i, "label": lab} for lab, i in cands},
                   "clarification": {"question": f"Which '{shown}' do you mean?",
                                     "options": [{"label": f"{public(i)} ({lab})"} for lab, i in cands],
                                     "answer": next(f"{public(i)} ({lab})" for lab, i in cands if i == intended_sto)}}))
        amb += 1

    # ---- out of coverage: needs an operator the catalog lacks ----
    live_anchors = sorted({(s.label, public(a), s.target) for s, a in jobs})
    rng.shuffle(live_anchors)
    templates = {
        "path_search": "What is the shortest chain of relationships that connects {a} and {b}?",
        "temporal_trend": "How has the number of {target} entries linked to {a} changed from year to year?",
        "statistical_median": "What is the median number of {target} entries per {label} in the catalogue?",
        "similarity": "Which {label} is most similar to {a}?",
    }
    oc = 0
    for i, (label, a, target) in enumerate(live_anchors):
        if oc >= cfg.out_of_coverage:
            break
        op = MISSING_OPERATORS[oc % len(MISSING_OPERATORS)]
        b = None
        if op == "path_search":
            others = [x for x in live_anchors if x[1] != a and split_of(ds, x[1]) == split_of(ds, a)]
            if not others:
                continue
            b = others[0][1]
        text = plain_template_text(card, templates[op].format(a=a, b=b, target=target, label=label))
        qid = "CG-" + hashlib.sha1(f"ooc|{op}|{a}|{b}".encode()).hexdigest()[:12]
        out.questions.append(_bank_entry(ds, qid, text, None, a, [], kind="out_of_coverage", tier="identifier",
                                         split=split_of(ds, a),
                                         extra={"gold_status": "not_expressible", "missing_operator": op,
                                                "other_anchor": b}))
        oc += 1
    out.notes.append(f"{len(slots)} slots, {len(jobs)} anchor draws, {len(empties)} slots with zero-degree anchors")
    if out.absent_slots:
        out.notes.append(f"{len(out.absent_slots)} card slots have no edge anywhere in the store: "
                         + ", ".join(out.absent_slots))
    return out


# --------------------------------------------------------------------------- #
# Checks (used by the step's validation script and its tests)
# --------------------------------------------------------------------------- #


def anchors_of(q: dict) -> set[str]:
    cg = q["card_gen"]
    out = {cg["anchor"]} if cg.get("anchor") else set()
    if cg.get("ambiguity") == "entity":
        out |= set(cg.get("readings") or {})
    if cg.get("other_anchor"):
        out.add(cg["other_anchor"])
    return out


def split_overlap(questions: list[dict]) -> set[str]:
    """Anchors appearing in both splits (must be empty)."""
    seen: dict[str, set[str]] = defaultdict(set)
    for q in questions:
        for a in anchors_of(q):
            seen[a].add(q["split"])
    return {a for a, s in seen.items() if len(s) > 1}


def leak_audit(card: dict, questions: list[dict]) -> list[dict]:
    """Re-run the automatic leak checks on the final text of every synonym and schema question."""
    bad = []
    for q in questions:
        cg = q["card_gen"]
        slot = cg.get("slot") or {}
        if cg["tier"] == "synonym_relation":
            leaks = leaked_stems(q["question"], forbidden_relation_stems(card, slot["rel"]))
        elif cg["tier"] == "paraphrased_schema":
            leaks = leaked_stems(q["question"], forbidden_label_stems(slot["target"])) + format_hints(q["question"])
        else:
            continue
        if leaks:
            bad.append({"id": q["id"], "tier": cg["tier"], "leaks": leaks})
    return bad


def write_banks(questions: list[dict], root: Any, name: str, meta: dict) -> dict[str, dict]:
    """``<root>/<name>-<dataset>-<decision>-<split>/bank.json``; returns {bank: {n, sha256}}."""
    from pathlib import Path

    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for q in questions:
        groups[(q["task"]["source"], q["card_gen"]["decision"], q["split"])].append(q)
    index = {}
    for (ds, decision, split), qs in sorted(groups.items()):
        bank = f"{name}-{ds}-{decision}-{split}"
        path = Path(root) / bank / "bank.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        body = {"meta": {**meta, "dataset": ds, "decision": decision, "split": split,
                         "sealed": split == "heldout", "count": len(qs)},
                "questions": sorted(qs, key=lambda q: q["id"])}
        text = json.dumps(body, indent=1, sort_keys=True)
        path.write_text(text)
        index[bank] = {"n": len(qs), "sha256": hashlib.sha256(text.encode()).hexdigest()}
    return index


__all__ = ["DECISION_OF_KIND", "DECISION_OF_TIER", "KINDS", "MISSING_OPERATORS", "TIERS", "GenConfig",
           "Generated", "Slot", "anchors_of", "card_slots", "forbidden_label_stems", "forbidden_relation_stems",
           "generate", "is_public_id", "leak_audit", "leaked_stems", "plain_label", "plain_template_text",
           "plural", "question_problems",
           "question_rules", "reference_entry", "reference_problems", "schema_label_copied", "split_of", "split_overlap", "words_of",
           "write_banks", "write_question", "write_reference"]
