# Figure Sources

The generator for every **promoted** figure — the ones destined for the paper.
Per-experiment figures keep their generators beside them, in
`experiments/EXP-*/figures/make_figures.py`.

```bash
make figures            # regenerate everything
uv run python scripts/make_figures.py --check   # fail if any output is stale
```

`--check` is what CI runs. If a generator no longer reproduces its committed
output byte-for-byte, the figure is stale and must not reach the paper.

| Figure | Generator | Source experiment(s) |
|---|---|---|
| `fig-arm-comparison.{svg,pdf}` | [`make_arm_comparison.py`](make_arm_comparison.py) | EXP-2026-07-001 … -007 |
| `fig01-architecture.{svg,pdf}` | [`make_architecture.py`](make_architecture.py) | — (see exception below) |
| `../../tables/tab-component.{md,tex}` | [`../../tables/sources/make_component_table.py`](../../tables/sources/make_component_table.py) | EXP-2026-07-008 |

## Rules

- **Read numbers from `data/metrics.json`.** Never hardcode a value in a
  plotting script. A figure whose numbers live in the plotting code silently
  stops matching the experiment it claims to show.
- **Emit both `.svg` and `.pdf`.** Raster `.png` only for genuine bitmaps, and
  even then keep the generator.
- **Deterministic output.** Generators here write SVG by hand rather than through
  a plotting library — matplotlib embeds element ids and creation dates that
  change on every run and would make `--check` useless. PDF conversion goes
  through [`_svg2pdf.py`](_svg2pdf.py), which pins `SOURCE_DATE_EPOCH` so
  `rsvg-convert` stops embedding a live timestamp in the PDF Info dictionary.
  Without that pin, two conversions of the *same* SVG differ by ~560 bytes and
  CI fails on the clock rather than on the figures. **Always convert through that
  helper**, never by calling `rsvg-convert` directly.
- **Colour-blind-safe palette, and colour is never the only encoding.** Every bar
  in `fig-arm-comparison` carries its arm letter and its value as text.
- **No font below 7pt at final print size.** The smallest in use is 8pt.
- **Record the source experiment ID** in a header comment.

## The one exception

`fig01-architecture` is a **system diagram, not a plot of data**. §4 of
[`../../AGENT_INSTRUCTIONS.md`](../../AGENT_INSTRUCTIONS.md) explicitly permits
architecture diagrams authored as SVG and committed with their source, and here
the SVG *is* the source — it lives at `docs/assets/architecture.svg` and is
hand-authored.

It is not exempt from reproducibility, only from computation:
[`make_architecture.py`](make_architecture.py) re-derives both promoted outputs
from the authored source, so the promoted copy cannot drift, and `--check` fails
if anyone hand-edits it. Binary-only diagram exports remain rejected.

## Promoting a figure

A figure moves here only when it is destined for the paper. Promotion copies the
figure **and** its generator, and records the source experiment ID in a header
comment. Update the table above in the same commit.
