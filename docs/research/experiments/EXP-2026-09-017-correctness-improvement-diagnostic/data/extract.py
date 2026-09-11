"""Extract only EXP-005's two original qwen positions; never regrade answers."""
import csv
import hashlib
import json
from pathlib import Path
from statistics import mean

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
SOURCE = ROOT / 'docs/evaluation/composition/bank/post-repair-generic.json'
RAW = ROOT / 'docs/evaluation/experiments/post-repair-2026-09-03'
RELATIONS = ('HAS_ALTERNATE_TERM', 'HAS_EXAMPLE', 'HAS_INDICATOR',
             'HAS_PREREQUISITE', 'REQUIRES_RESOURCE')


def main():
    rows = json.loads(SOURCE.read_text())['rows']
    sources = []
    def read(path):
        raw = path.read_bytes()
        sources.append({'path': str(path.relative_to(ROOT)), 'bytes': len(raw),
                        'sha256': hashlib.sha256(raw).hexdigest()})
        return json.loads(raw)
    read(SOURCE)
    extracted = []
    for row in rows:
        assert row['split'] == 'dev'
        item = {k: row[k] for k in ('id', 'd_tier', 'register')}
        item['missing_pattern'] = int(any(
            f'-[{relation}]->' in shape
            for relation in RELATIONS for shape in row['shapes']))
        for arm in ('generic', 'deterministic'):
            for pos, suffix in ((1, ''), (2, '.pass2')):
                path = RAW / arm / 'answers' / f"{row['id']}.judgment{suffix}.json"
                verdict = read(path)
                assert verdict['case_id'] == row['id']
                value = float(verdict['correctness'])
                assert 0 <= value <= 1
                item[f'{arm}_{pos}'] = value
        extracted.append(item)
    assert len(extracted) == len({r['id'] for r in extracted})
    published = read(ROOT / 'docs/evaluation/composition/bank/post-repair-judged.json')
    for arm in ('generic', 'deterministic'):
        assert len(extracted) == published[arm]['cases_judged']
        actual = mean(mean(r[f'{arm}_{p}'] for p in (1, 2)) for r in extracted)
        assert round(actual, 4) == published[arm]['mean_correctness']
    with (HERE / 'cases.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(extracted[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(extracted)
    (HERE / 'source_hashes.json').write_text(json.dumps(sources, indent=2) + '\n')
    pointers = ['# Sources', '', 'All original judgment files are individually hashed in `source_hashes.json`.',
                'The compact CSV is sufficient to regenerate the analysis without raw sidecars.', '',
                '| Artifact | Path | Bytes | Hash |', '|---|---|---:|---|']
    for path in (SOURCE, HERE / 'source_hashes.json', HERE / 'cases.csv'):
        raw = path.read_bytes()
        pointers.append(f'| {path.name} | `{path.relative_to(ROOT)}` | {len(raw)} | `sha256:{hashlib.sha256(raw).hexdigest()}` |')
    (HERE / 'POINTERS.md').write_text('\n'.join(pointers) + '\n')
    print('Extracted paired original judgments; published means reproduced.')


if __name__ == '__main__':
    main()
