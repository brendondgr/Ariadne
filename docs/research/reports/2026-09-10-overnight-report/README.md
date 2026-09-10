# 2026-09-10 overnight report — generator

`build.py` writes `report.html`; the PDF is rendered from it with headless
Chromium. Every number and every figure is read from a committed data file at
build time — `data.py` lists exactly which ones — so the report cannot drift
from the experiments it describes, and re-running it after an amendment
produces the corrected document rather than a stale one.

```
uv run python docs/research/reports/2026-09-10-overnight-report/build.py
chromium-browser --headless --no-pdf-header-footer \
  --print-to-pdf=report.pdf file://$PWD/report.html
```

Sections whose data is missing render as "not yet complete" rather than
failing, which is what let the report be written while the runs were still
going. If a section says that in the committed PDF, the run did not finish.
