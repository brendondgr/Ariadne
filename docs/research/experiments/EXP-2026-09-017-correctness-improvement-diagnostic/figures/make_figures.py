"""Rebuild EXP-017 from its committed paired scores. No live pipeline or judge."""
import csv
import json
import os
from pathlib import Path
from statistics import mean

os.environ.setdefault('MPLCONFIGDIR', '/tmp/ariadne-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

EXP = Path(__file__).resolve().parents[1]
LABELS = {'D0': 'Abstention probes', 'D1': 'Property reads',
          'D2': 'One hop, forward', 'D3': 'One hop, reverse',
          'D4': 'Two hops', 'D5': 'Constrained queries', 'D6': 'Cross-source chains'}
ARMS = ('generic', 'deterministic')


def aggregate():
    rows = list(csv.DictReader((EXP / 'data/cases.csv').open()))
    for row in rows:
        for arm in ARMS:
            row[arm] = mean(float(row[f'{arm}_{p}']) for p in (1, 2))
    n = len(rows)
    values = {}
    def metric(key, value, count):
        values[key] = {'mean': value, 'std': None, 'n': count}
        return value
    overall = {a: metric(a + '_judged', mean(r[a] for r in rows), n) for a in ARMS}
    tiers = []
    for tier, label in LABELS.items():
        subset = [r for r in rows if r['d_tier'] == tier]
        item = {'tier': tier, 'label': label, 'n': len(subset)}
        for arm in ARMS:
            item[arm] = metric(f'{tier}_{arm}', mean(r[arm] for r in subset), len(subset))
        item['headroom'] = metric(f'{tier}_generic_headroom', sum(1-r['generic'] for r in subset)/n, len(subset))
        tiers.append(item)
    assert abs(sum(t['headroom'] for t in tiers) - (1-overall['generic'])) < 1e-12
    blocked = [r for r in rows if r['missing_pattern'] == '1']
    other = [r for r in rows if r['missing_pattern'] == '0']
    slice_mean = metric('missing_pattern_generic', mean(r['generic'] for r in blocked), len(blocked))
    other_mean = metric('other_generic', mean(r['generic'] for r in other), len(other))
    scenarios = []
    # These are explicitly hypothetical targets, not measurements.
    for target in (0.5, 0.75, 1.0):
        score = overall['generic'] + len(blocked)/n * (target-slice_mean)
        metric(f'scenario_slice_{target:.2f}', score, n)
        scenarios.append({'target': target, 'overall': score})
    values.update(json.loads((EXP / 'data/context.json').read_text())['manifest_metrics'])
    data = {'experiment': 'EXP-2026-09-017', 'n': n, 'overall': overall, 'tiers': tiers,
            'missing_pattern': {'n': len(blocked), 'mean': slice_mean, 'other_mean': other_mean},
            'scenarios': scenarios, 'manifest_metrics': values,
            'interpretation': 'Descriptive headroom, not causal attribution. Scenarios hold all other scores fixed. No confidence intervals estimated.'}
    (EXP / 'data/metrics.json').write_text(json.dumps(data, indent=2)+'\n')


def render():
    data = json.loads((EXP / 'data/metrics.json').read_text())
    tiers = data['tiers']
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'pdf.fonttype': 42, 'svg.fonttype': 'path'})
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.6), gridspec_kw={'width_ratios': [1.55, 1]})
    fig.patch.set_facecolor('#fafaf7')
    y = np.arange(len(tiers))
    for ax in axes:
        ax.set_facecolor('#fafaf7')
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_axisbelow(True)
        ax.xaxis.grid(True, alpha=.2)
        ax.tick_params(length=0)
    ax = axes[0]
    for arm, offset, color, hatch in [('generic', -.18, '#0072B2', ''), ('deterministic', .18, '#b55f00', '//')]:
        vals = [t[arm] for t in tiers]
        bars = ax.barh(y+offset, vals, .32, color=color, hatch=hatch,
                       label='Schema-derived' if arm == 'generic' else 'Templates')
        ax.bar_label(bars, labels=[f'{v:.3f}' for v in vals], padding=4, fontsize=9)
    ax.set_yticks(y, [f"{t['tier']}  {t['label']}  (n={t['n']})" for t in tiers])
    ax.invert_yaxis()
    ax.set_xlim(0, 1.12)
    ax.set_xticks([0, .25, .5, .75, 1])
    ax.set_xlabel('Mean judged correctness (fractional score)')
    ax.set_title('Where the system succeeds and struggles', loc='left', fontsize=13, pad=18)
    ax.legend(loc='lower center', bbox_to_anchor=(.5, -.26), ncols=2, frameon=False)
    ranked = sorted(tiers, key=lambda t: t['headroom'], reverse=True)
    ax = axes[1]
    bars = ax.barh(np.arange(len(ranked)), [t['headroom'] for t in ranked], color='#0072B2')
    ax.bar_label(bars, labels=[f"+{t['headroom']:.4f}" for t in ranked], padding=4, fontsize=10)
    ax.set_yticks(np.arange(len(ranked)), [t['tier'] for t in ranked])
    ax.invert_yaxis()
    ax.set_xlim(0, max(t['headroom'] for t in ranked)*1.4)
    ax.set_xlabel('Maximum addition to overall score')
    ax.set_title('Headroom if a whole category\nbecame perfect', loc='left', fontsize=13, pad=18)
    fig.suptitle(f"Ariadne: what sits behind {data['overall']['generic']:.4f}?", x=.03, ha='left', fontsize=22, fontweight='bold')
    fig.text(.03, .885, f"Development set · {data['n']} paired questions · original qwen judgments · two grading positions per answer", fontsize=11)
    fig.text(.03, .025, 'Source: EXP-2026-09-005 → EXP-2026-09-017. Headroom is arithmetic, not a predicted gain.\nCategory means are descriptive; uncertainty intervals are not estimated. D0 tests appropriate abstention.', fontsize=9, color='#444444')
    fig.subplots_adjust(left=.26, right=.96, top=.78, bottom=.23, wspace=.32)
    for ext in ('svg', 'pdf'):
        fig.savefig(EXP / f'figures/fig-correctness-opportunities.{ext}', metadata={'Creator': 'EXP-2026-09-017'})
    plt.close(fig)
    table = ['| Category | Questions | Schema-derived | Templates | Overall headroom |', '|---|---:|---:|---:|---:|']
    for t in tiers:
        table.append(f"| {t['tier']} {t['label']} | {t['n']} | {t['generic']:.4f} | {t['deterministic']:.4f} | +{t['headroom']:.4f} |")
    table += ['', '| CAPEC slice target (hypothetical) | Overall score, all other cases fixed |', '|---|---:|']
    table += [f"| {s['target']:.2f} | {s['overall']:.4f} |" for s in data['scenarios']]
    (EXP / 'tables/results.md').write_text('\n'.join(table)+'\n')
    svg = (EXP / 'figures/fig-correctness-opportunities.svg').read_text()
    svg = svg[svg.index('<svg'):]
    html = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ariadne correctness opportunities</title><style>body{font:18px/1.6 system-ui,sans-serif;max-width:1200px;margin:40px auto;padding:0 24px;background:#fafaf7;color:#172330}h1{line-height:1.15}svg{width:100%;height:auto}.card{padding:24px;border:1px solid #aab5bd;border-radius:12px;margin:24px 0}input{width:100%;min-height:44px}output{display:block;font-size:24px;font-weight:700}a{color:#005a91}table{border-collapse:collapse;font-size:15px}td,th{padding:8px;text-align:left;border-bottom:1px solid #aaa}</style>
<h1>Where can Ariadne improve?</h1><p>The bars show existing judgments. The right panel prices the remaining score in each category; it does not promise a fix will recover it.</p>
FIGURE
<div class="card"><h2>Explore the blocked CAPEC relationship slice</h2><p id="slice"></p><label for="target">Hypothetical mean correctness after repair</label><input id="target" type="range" min="0" max="1" step="0.01" value="0.5"><output id="score" for="target" aria-live="polite"></output><p>Assumes every other answer keeps its original score. This is a sensitivity calculation, not an experiment or forecast. A gate repair may still leave planning and answer-composition failures.</p></div>
<p><a href="RESULTS.md">Read the diagnosis and proposed experiments</a> · <a href="figures/fig-correctness-opportunities.pdf">Download the chart as PDF</a> · <a href="data/metrics.json">Inspect the data</a></p>
<script>const d=DATA;const s=d.missing_pattern;document.getElementById('slice').textContent=`${s.n} of ${d.n} development questions touch the missing edge patterns. Their measured judge mean is ${s.mean.toFixed(4)}; the remaining cases average ${s.other_mean.toFixed(4)}.`;const input=document.getElementById('target');function update(){const target=Number(input.value);const total=d.overall.generic+s.n/d.n*(target-s.mean);document.getElementById('score').textContent=`Slice mean ${target.toFixed(2)} → overall ${total.toFixed(4)} (${total>=d.overall.generic?'+':''}${(total-d.overall.generic).toFixed(4)})`;}input.addEventListener('input',update);update();</script></html>'''
    (EXP / 'explorer.html').write_text(html.replace('FIGURE', svg).replace('DATA', json.dumps(data)))
    print(json.dumps({'overall': data['overall'], 'tiers': tiers, 'missing_pattern': data['missing_pattern'], 'scenarios': data['scenarios']}, indent=2))


if __name__ == '__main__':
    aggregate()
    render()
