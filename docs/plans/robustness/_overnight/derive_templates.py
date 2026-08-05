"""Task 7 — derive the template count mechanically.

Counts `template="..."` literals per builder, maps each to the method that emits
it, walks the call graph from each public entry point to decide reachability,
and scans the question banks for `expected_template`.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

BUILDERS = {
    "cypher": Path("utils/specialists/cypher/builder.py"),
    "gremlin": Path("utils/specialists/gremlin/builder.py"),
}
BANKS = [
    Path("utils/specialists/tests/golden/attack_questions.json"),
    Path("utils/specialists/tests/golden/capec_questions.json"),
    Path("utils/specialists/tests/golden/federated_questions.json"),
]
ENTRY_POINTS = ["build", "expand"]


def builder_class(tree: ast.Module) -> ast.ClassDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name.endswith("QueryBuilder"):
            return node
    raise SystemExit("no *QueryBuilder class found")


def analyse(path: Path) -> dict:
    tree = ast.parse(path.read_text())
    cls = builder_class(tree)
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}

    # method -> the template literals it emits, and the self.* methods it calls
    emits: dict[str, list[str]] = {}
    calls: dict[str, set[str]] = {}
    returns_draft: set[str] = set()
    for name, fn in methods.items():
        emits[name] = []
        calls[name] = set()
        for node in ast.walk(fn):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "QueryDraft":
                    returns_draft.add(name)
                    for kw in node.keywords:
                        if kw.arg == "template" and isinstance(kw.value, ast.Constant):
                            emits[name].append(kw.value.value)
                if (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "self"
                ):
                    calls[name].add(node.func.attr)
            # a method that returns another method's draft is also a draft path
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Call):
                f = node.value.func
                if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "self":
                    returns_draft.add(name)

    # reachable methods, per entry point
    def reach(entry: str) -> set[str]:
        seen: set[str] = set()
        stack = [entry]
        while stack:
            m = stack.pop()
            if m in seen or m not in methods:
                continue
            seen.add(m)
            stack.extend(calls[m])
        return seen

    reachable_by_entry = {e: reach(e) for e in ENTRY_POINTS if e in methods}
    reachable = set().union(*reachable_by_entry.values())

    literal_to_method = {}
    for m, ts in emits.items():
        for t in ts:
            literal_to_method.setdefault(t, []).append(m)

    all_literals = sorted(literal_to_method)
    dead = sorted(t for t, ms in literal_to_method.items() if not any(m in reachable for m in ms))

    return {
        "file": str(path),
        "template_literals": all_literals,
        "template_literal_count": len(all_literals),
        "literal_to_method": {t: sorted(ms) for t, ms in sorted(literal_to_method.items())},
        "querydraft_returning_methods": sorted(returns_draft),
        "querydraft_returning_method_count": len(returns_draft),
        "reachable_from": {e: sorted(t for t, ms in literal_to_method.items()
                                     if any(m in reachable_by_entry[e] for m in ms))
                           for e in reachable_by_entry},
        "unreachable_templates": dead,
    }


def main() -> None:
    per_builder = {name: analyse(p) for name, p in BUILDERS.items()}

    cy = set(per_builder["cypher"]["template_literals"])
    gr = set(per_builder["gremlin"]["template_literals"])
    shared = sorted(cy & gr)
    union = sorted(cy | gr)

    exercised: dict[str, set[str]] = {}
    for bank in BANKS:
        data = json.loads(bank.read_text())
        found: set[str] = set()

        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k == "expected_template" and isinstance(v, str):
                        found.add(v)
                    else:
                        walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)

        walk(data)
        exercised[bank.name] = found

    all_exercised = sorted(set().union(*exercised.values()))
    unknown = sorted(t for t in all_exercised if t not in cy | gr)

    out = {
        "_derivation": {
            "method": (
                "AST parse of each builder: every QueryDraft(template=\"...\") "
                "literal, the method emitting it, the self.* call graph from the "
                "public entry points (build, expand), and a scan of every "
                "`expected_template` value in the three question banks. Counted, "
                "not read off prose."
            ),
            "generated_at": "2026-08-04",
        },
        "per_builder": per_builder,
        "shared_names": shared,
        "distinct_identifiers_union": union,
        "distinct_identifier_count": len(union),
        "cypher_count": len(cy),
        "gremlin_count": len(gr),
        "exercised_by_bank": {k: sorted(v) for k, v in exercised.items()},
        "exercised_union": all_exercised,
        "exercised_count": len(all_exercised),
        "exercised_but_not_a_builder_template": unknown,
        "declared_but_not_exercised": sorted(set(union) - set(all_exercised)),
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
