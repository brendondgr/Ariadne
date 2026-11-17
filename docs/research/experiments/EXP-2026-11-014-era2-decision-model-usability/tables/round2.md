# Round 2 (EXP-2026-11-014, amendment 2)

Each treatment against the named comparison, same items: accuracy with a 95% interval over anchors;
gate coverage as the median per-split difference. Flip for averaged treatments compares the pick from
orders 0+1 with the pick from orders 2+3.

| Decision | Treatment | n | Accuracy | Against | Δ accuracy | Δ none recall | Gate: coverage, wrong (p90) | Δ gate coverage | Flip | Gated = Qwen | Role |
|---|---|---:|---:|---|---|---|---|---|---:|---:|---|
| D4 | pplx_single | 464 | 0.7284 | — | — | — | 0.1293, 0.05 (0.0517) | — | 0.0668 | 1.0 | second opinion |
| D4 | pplx_avg2 | 464 | 0.7306 | pplx_single | +0.002 [-0.009, +0.013] | +0.000 [+0.000, +0.000] | 0.1358, 0.0476 (0.0492) | +0.006 [-0.011, +0.011] | 0.0474 | 1.0 | second opinion |
| D4 | d3_single | 464 | 0.6336 | — | — | — | 0.2198, 0.049 (0.051) | — | 0.1336 | 0.9804 | not used |
| D4 | d3_avg2 | 464 | 0.6315 | d3_single | -0.002 [-0.024, +0.019] | +0.020 [-0.025, +0.074] | 0.222, 0.0485 (0.0505) | +0.002 [+0.000, +0.041] | 0.0754 | 0.9806 | gate |
| D4 | duo | 464 | 0.7328 | pplx_single | +0.004 [-0.007, +0.017] | +0.010 [-0.042, +0.064] | 0.181, 0.0476 (0.0494) | +0.052 [+0.046, +0.060] | 0.0711 | 0.9881 | second opinion |
| D4 | duo_avg2 | 464 | 0.7457 | pplx_avg2 | +0.015 [-0.004, +0.035] | +0.010 [-0.047, +0.074] | 0.1509, 0.0429 (0.0448) | +0.015 [+0.009, +0.045] | 0.0323 | 0.9714 | second opinion |
| D2+D3 | pplx_single | 397 | 0.6952 | — | — | — | 0.2015, 0.0494 (0.0533) | — | 0.1234 | 1.0 | second opinion |
| D2+D3 | pplx_avg2 | 397 | 0.6826 | pplx_single | -0.013 [-0.030, +0.003] | -0.031 [-0.077, +0.008] | 0.2091, 0.0488 (0.055) | +0.009 [+0.003, +0.063] | 0.0856 | 1.0 | gate |
| D2+D3 | d3_single | 397 | 0.6851 | — | — | — | 0.262, 0.0485 (0.0515) | — | 0.1108 | 0.9615 | second opinion |
| D2+D3 | d3_avg2 | 397 | 0.6776 | d3_single | -0.008 [-0.028, +0.013] | -0.015 [-0.059, +0.026] | 0.2796, 0.0455 (0.0476) | +0.018 [+0.013, +0.060] | 0.0756 | 0.973 | gate |
| D2+D3 | duo | 397 | 0.7355 | pplx_single | +0.040 [+0.015, +0.068] | +0.008 [-0.032, +0.049] | 0.4131, 0.0491 (0.0519) | +0.209 [+0.163, +0.247] | 0.063 | 0.9695 | gate |
| D2+D3 | duo_avg2 | 397 | 0.733 | pplx_avg2 | +0.050 [+0.023, +0.080] | +0.031 [-0.008, +0.077] | 0.4184, 0.0485 (0.0513) | +0.209 [+0.144, +0.235] | 0.0529 | 0.9699 | gate |

Items with only two real options (their averaged flip measures server noise only): D4 28 of 464, D2+D3 2 of 397

## Readings shortlist (pplx shortlists from its wording records)

| Test recall (median; p10) | List size (median) | Chooser | Gold kept | Accuracy | Δ vs same chooser, full readings menu | Δ none recall | Gate: coverage, wrong (p90) | Flip | Gated = Qwen | Role |
|---|---:|---|---:|---:|---|---|---|---:|---:|---|
| 0.9534; 0.9522 | 1.403 | pplx | 0.9634 | 0.7112 | -0.017 [-0.040, +0.007] | -0.040 [-0.086, +0.000] | 0.3125, 0.0483 (0.0496) | 0.0603 | 0.9862 | gate |
| 0.9534; 0.9522 | 1.403 | d3 | 0.9634 | 0.6509 | +0.017 [-0.030, +0.067] | +0.343 [+0.227, +0.468] | 0.0108, 0.0 (0.0) | 0.0603 | 1.0 | not used |
