"""Re-issue the generic fallback audit with ANSWER denominators (A-8).

The 2026-09-10 audit divided the fallback count by the number of *files* in each
answer directory. Those directories also hold two or more judgment sidecars per
answer, so the denominators were three to five times too large and every rate
came out three to five times too small. This script counts answers only, and
also breaks the fallback reasons out by seam so a narrator time-out is not read
as a dead specialist seam.
"""
import collections
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[4]
OUT = HERE / 'generic_fallback_audit.json'

RUNS = {
    'EXP-2026-09-005 post-repair dev': 'docs/evaluation/experiments/post-repair-2026-09-03/generic/answers',
    'EXP-2026-09-007 holdout': 'docs/evaluation/experiments/holdout-spend-2026-09-05/generic/answers',
    'EXP-2026-09-002 expansion': 'docs/evaluation/experiments/expansion-judged-2026-09-01/generic/answers',
}
# The two references were already computed over answers and are unchanged.
REFERENCE = {
    'degraded_30s': {'fallback': 198, 'answers': 284, 'rate': 0.6972},
    'healthy_4096s': {'fallback': 39, 'answers': 284, 'rate': 0.1373},
}


def audit(directory):
    files = sorted((ROOT / directory).glob('*.json'))
    answers = [f for f in files if '.judgment' not in f.name]
    reasons = collections.Counter()
    for path in answers:
        reason = (json.loads(path.read_text()).get('answer') or {}).get('fallback_reason')
        if reason:
            reasons[reason.split('(')[0].strip()] += 1
    fallback = sum(reasons.values())
    return {
        'files_in_directory': len(files),
        'answers': len(answers),
        'fallback_reason': fallback,
        'rate': round(fallback / len(answers), 4),
        'rate_over_files_2026_09_10': round(fallback / len(files), 4),
        'reasons': dict(reasons),
        'verdict': ('healthy' if fallback / len(answers) <= REFERENCE['healthy_4096s']['rate']
                    else 'above the healthy reference'),
    }


def main():
    audited = {name: audit(directory) for name, directory in RUNS.items()}
    OUT.write_text(json.dumps({
        'reference': REFERENCE,
        'audited': audited,
        'conclusion': (
            'Corrected 2026-09-11 (A-8). The 2026-09-10 issue of this file divided the '
            'fallback count by the number of FILES in each answer directory, which also '
            'holds two or more judgment sidecars per answer. Against answer denominators '
            'the rates are 0.43 (dev), 0.30 (holdout) and 0.07 (expansion) against a '
            'healthy reference of 0.14 and a degraded one of 0.70. Two of the three runs '
            'behind C-023 sit above the healthy reference, so the earlier sentence "no '
            'published figure is affected" was reached by arithmetic that does not hold. '
            'Every fallback in all three runs is a narrator read time-out at the 120 s '
            'SYNTHESIS_LLM_TIMEOUT_S default; none is a planner or specialist seam '
            'failure, so the arm identity finding of I-4 is not what these rates show.'),
    }, indent=2) + '\n')
    for name, row in audited.items():
        print(f"{name}: {row['fallback_reason']}/{row['answers']} = {row['rate']} "
              f"(was {row['rate_over_files_2026_09_10']} over {row['files_in_directory']} files) "
              f"— {row['verdict']}")


if __name__ == '__main__':
    main()
