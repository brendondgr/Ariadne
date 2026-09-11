"""Summarise the pre-repair model-free reference captures (Step 0).

The answers themselves are gitignored raw run output (D-033), so what is
committed is this summary: a per-case digest of the answer with the clock keys
stripped, plus gold coverage and record counts. Every model-free diff in
Steps 1-4 is `--diff` against this file, which is the recorded-answer regression
the repository requires before any builder or composer change ships.
"""
import argparse
import hashlib
import json
import pathlib
from statistics import mean

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[5]
SUMMARY = HERE / 'reference.json'

CAPTURES = {
    ('dev', 'deterministic'): 'docs/evaluation/experiments/repair-reference-2026-09-11-dev/deterministic/answers',
    ('dev', 'generic_composed'): 'docs/evaluation/experiments/repair-reference-2026-09-11-dev/generic_composed/answers',
    ('holdout', 'deterministic'): 'docs/evaluation/experiments/repair-reference-2026-09-11-holdout/deterministic/answers',
    ('holdout', 'generic_composed'): 'docs/evaluation/experiments/repair-reference-2026-09-11-holdout/generic_composed/answers',
}

# Keys whose value moves between identical runs. Stripped before digesting, so a
# digest difference means the ANSWER changed, not that the clock did.
# The canonical pair is `scripts/generic_identity_rerun.py`'s CLOCK; the rest are
# defensive, for keys a future run might surface.
CLOCK_KEYS = {'timing_ms', 'wall_s', 'elapsed_s', 'duration_s', 'started_at',
              'finished_at', 'timestamp', 'generated_at', 'latency_ms', 'took_ms'}


def strip_clock(node, key=None):
    """Drop clock keys, and sort `facets` lists into a canonical order.

    Facet order is not stable across a fixture reload: re-running the
    `deterministic` arm at the same commit reproduced 224 of 284 dev answers
    byte-for-byte and the other 60 differed only by a facet moving position,
    with gold coverage identical on all 60. Within one session the same arm is
    284/284 identical. Sorting facets makes the digest answer "did the answer
    change", which is the question the regression asks; ISSUES I-1 records the
    unsorted reading so the instability itself is not hidden.
    """
    if isinstance(node, dict):
        return {k: strip_clock(v, k) for k, v in node.items() if k not in CLOCK_KEYS}
    if isinstance(node, list):
        items = [strip_clock(v) for v in node]
        if key == 'facets':
            items.sort(key=lambda v: json.dumps(v, sort_keys=True))
        return items
    return node


def digest(answer):
    stable = strip_clock(answer)
    return hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()[:16]


def summarise(directory):
    cases = {}
    for path in sorted((ROOT / directory).glob('*.json')):
        if '.judgment' in path.name:
            continue
        answer = json.loads(path.read_text())
        results = (answer.get('logic_flow') or {}).get('results') or []
        coverage = (answer.get('deterministic_scores') or {}).get('coverage') or {}
        cases[answer['id']] = {
            'digest': digest(answer),
            'records': sum(len(r.get('records') or []) for r in results),
            'gold': coverage.get('gold'),
            'found': coverage.get('found'),
            'coverage': coverage.get('coverage'),
            'claims': len((answer.get('answer') or {}).get('claims') or []),
            'abstentions': len((answer.get('answer') or {}).get('abstentions') or []),
            'fallback_reason': (answer.get('answer') or {}).get('fallback_reason'),
        }
    return cases


def build():
    out = {'note': __doc__.strip().splitlines()[0], 'captures': {}}
    for (split, arm), directory in CAPTURES.items():
        cases = summarise(directory)
        covs = [c['coverage'] for c in cases.values() if c['coverage'] is not None]
        out['captures'][f'{split}/{arm}'] = {
            'directory': directory,
            'n': len(cases),
            'mean_coverage': round(mean(covs), 6) if covs else None,
            'zero_record_cases': sum(1 for c in cases.values() if c['records'] == 0),
            'fallbacks': sum(1 for c in cases.values() if c['fallback_reason']),
            'cases': cases,
        }
    SUMMARY.write_text(json.dumps(out, indent=1, sort_keys=True) + '\n')
    for name, cap in out['captures'].items():
        print(f"{name:28s} n={cap['n']:3d} mean_coverage={cap['mean_coverage']} "
              f"zero_record={cap['zero_record_cases']:3d} fallbacks={cap['fallbacks']}")


def diff():
    """Compare the current captures against the committed reference."""
    reference = json.loads(SUMMARY.read_text())['captures']
    changed_total = 0
    for (split, arm), directory in CAPTURES.items():
        name = f'{split}/{arm}'
        now, before = summarise(directory), reference[name]['cases']
        changed = [cid for cid in before if before[cid]['digest'] != now.get(cid, {}).get('digest')]
        changed_total += len(changed)
        gained = sum(1 for c in changed if now[c]['coverage'] > (before[c]['coverage'] or 0))
        lost = sum(1 for c in changed if now[c]['coverage'] < (before[c]['coverage'] or 0))
        print(f'{name:28s} changed={len(changed):3d}  coverage gained={gained} lost={lost}')
        for cid in changed[:10]:
            print(f'    {cid}\n      records {before[cid]["records"]} -> {now[cid]["records"]}, '
                  f'coverage {before[cid]["coverage"]} -> {now[cid]["coverage"]}')
    return changed_total


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diff', action='store_true',
                        help='compare current captures against the committed reference')
    args = parser.parse_args()
    raise SystemExit(min(diff(), 1) if args.diff else (build() or 0))
