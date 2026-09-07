# Data pointers

No dataset. The inputs are twelve fixed question strings held in the probe
itself:

- `utils/tests/sse_gap_probe.py` — `QUESTIONS`

The outputs are the raw stream logs in `../logs/`, pinned by content hash:

- `logs/before-12way-events.log` — per-event arrival times, 12-way, pre-fix behaviour
  - `sha256:4a713e6a6cd3f9c1d4eb150a1a3e91720b12c5e5afb4a5488fc662add4da9079`
- `logs/after-run1-12way.log` — first post-fix probe; contains the 24-way outlier
  - `sha256:860f4e5c1482391d65482fb972d696907e449130e7e2bb74e3cba5b863c31b9b`
- `logs/after-run2-12way.log` — clean 12-way post-fix probe — the headline figure
  - `sha256:f0ff9af50518b49a2848cddc761b70cd8fbba633f2031e3a241ff217111e02bb`
- `logs/after-solo-frame-timings.log` — every frame of one run, keep-alives included
  - `sha256:755aef5e28c34978d117660c1e87897603a00b3f72e4c2a1bce56e2bcad63bf4`
- `logs/wedged-worker-pyspy.txt` — thread dump of the deadlocked worker
  - `sha256:f38510e3b932f859302de608605307ca62a34249c8483fe49f01480e475b9ea1`
