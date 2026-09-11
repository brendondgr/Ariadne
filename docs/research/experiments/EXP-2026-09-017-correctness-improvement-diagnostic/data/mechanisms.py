"""Assign each dev case to the first defect mechanism that applies (AMENDMENT A-2).

Reads only committed/derived inputs — this experiment's `cases.csv`, the dev
bank, and EXP-2026-09-005's saved generic answers. It never regrades anything:
the per-case scores come straight from `cases.csv`, so the generic and
deterministic means it prints are byte-for-byte the published 0.6569 / 0.4946.

The assignment is FIRST MATCH in the order below. The order is not arbitrary:
a case is attributed to the defect that would have to be repaired first for the
next one to be observable at all. A question whose edge is not allowlisted
never reaches a builder, so `capec` precedes `chain`; a walk whose seed binds to
the wrong namespace retrieves nothing to chain, so `ns` precedes `chain`; a
filter can only be mis-applied to records that came back, so `chain` precedes
`filter`; and a narrator time-out is only the *whole* story when no retrieval
defect is present, so `narrator` is last before `none`.
"""
import csv
import json
import pathlib
from statistics import mean

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CASES = HERE / 'cases.csv'
BANK = ROOT / 'docs/evaluation/composition/bank/bank-dev.json'
ANSWERS = ROOT / 'docs/evaluation/experiments/post-repair-2026-09-03/generic/answers'
OUT = HERE / 'mechanisms.csv'

# (name, predicate, one-line description) — evaluated in this order, first match wins.
MECHANISMS = [
    ('capec', lambda c: c['missing_pattern'] == 1,
     'One of the five CAPEC edges declared by the snapshot but absent from the card allowlist (Q45)'),
    ('ns', lambda c: c['anchor_label'] in ('Category', 'View') and c['d_tier'] != 'D0',
     'Category/View seed rewritten into the attack-pattern namespace by the generic walk (Q50)'),
    ('chain', lambda c: c['n_steps'] >= 2,
     'Two-hop request collapsed to the shortest schema path from the anchor (Q51)'),
    ('filter', lambda c: c['n_filters'] >= 1,
     'Declared property filter never reaches the query or the composer (Q52)'),
    ('empty', lambda c: c['d_tier'] == 'D0' and c['records'] > 0,
     'Records returned but the composer never states that the requested set is empty (Q53)'),
    ('narrator', lambda c: bool(c['fallback_reason']),
     'Narrator fell back with no other defect present (Q47)'),
]
NONE = ('none', 'No known defect and the narrator ran')


def load():
    cases = list(csv.DictReader(CASES.open()))
    bank = {q['id']: q for q in json.loads(BANK.read_text())['questions']}
    joined = []
    for row in cases:
        case_id = row['id']
        spec = bank[case_id]['spec']
        answer = json.loads((ANSWERS / f'{case_id}.json').read_text())
        results = (answer.get('logic_flow') or {}).get('results') or []
        coverage = (answer.get('deterministic_scores') or {}).get('coverage') or {}
        joined.append({
            'id': case_id,
            'd_tier': row['d_tier'],
            'register': row['register'],
            'missing_pattern': int(row['missing_pattern']),
            'anchor_label': spec['anchor_label'],
            'predicate_chain': '>'.join(
                ('<' if s.get('reverse') else '') + s['predicate'] for s in spec['steps']),
            'n_steps': len(spec['steps']),
            'filter': ';'.join(
                f"{f.get('property')}{f.get('op', 'eq')}{f.get('value')}"
                for f in (spec.get('filters') or [])),
            'n_filters': len(spec.get('filters') or []),
            'records': sum(len(r.get('records') or []) for r in results),
            'gold': coverage.get('gold'),
            'found': coverage.get('found'),
            'coverage': coverage.get('coverage'),
            'fallback_reason': ((answer.get('answer') or {}).get('fallback_reason') or '').split('(')[0].strip(),
            'generic': (float(row['generic_1']) + float(row['generic_2'])) / 2,
            'deterministic': (float(row['deterministic_1']) + float(row['deterministic_2'])) / 2,
        })
    return joined


def assign(case):
    for name, predicate, _ in MECHANISMS:
        if predicate(case):
            return name
    return NONE[0]


def main():
    cases = load()
    for case in cases:
        case['mechanism'] = assign(case)

    generic = mean(c['generic'] for c in cases)
    deterministic = mean(c['deterministic'] for c in cases)
    assert round(generic, 4) == 0.6569, generic
    assert round(deterministic, 4) == 0.4946, deterministic
    lost = sum(1 - c['generic'] for c in cases)

    fields = ['id', 'mechanism', 'd_tier', 'register', 'anchor_label', 'predicate_chain',
              'filter', 'records', 'gold', 'found', 'coverage', 'fallback_reason',
              'missing_pattern', 'n_steps', 'n_filters', 'generic', 'deterministic']
    with OUT.open('w') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator='\n',
                                extrasaction='ignore')
        writer.writeheader()
        writer.writerows(cases)

    print(f'n={len(cases)}  generic={generic:.4f}  deterministic={deterministic:.4f}  '
          f'points lost={lost:.2f}')
    print(f"{'mechanism':10s} {'n':>4s} {'generic':>8s} {'lost':>7s} {'share':>7s}")
    for name, _, _ in MECHANISMS + [(NONE[0], None, None)]:
        sel = [c['generic'] for c in cases if c['mechanism'] == name]
        sub = sum(1 - v for v in sel)
        print(f'{name:10s} {len(sel):4d} {mean(sel):8.4f} {sub:7.2f} {100 * sub / lost:6.1f}%')


if __name__ == '__main__':
    main()
