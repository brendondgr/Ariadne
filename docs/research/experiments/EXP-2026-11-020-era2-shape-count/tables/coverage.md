# Coverage per source (from docs/evaluation/shape-count-2026-11/counts.json)

Cumulative share covered after each stage; `outside` closes the row at 1.0.

| Source | n | today | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | gaps | outside |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev 284 | 284 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| gold 120 | 120 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| variants 579 | 579 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Step 6 tuning 433 | 433 | 0.9700 | 0.9700 | 0.9700 | 0.9700 | 0.9700 | 0.9700 | 0.9792 | 0.9861 | 0.9931 | 0.9931 | 1.0000 |
| AttackQA sample 600 | 600 | 0.5717 | 0.5717 | 0.5717 | 0.5717 | 0.9400 | 0.9400 | 0.9400 | 0.9400 | 0.9400 | 0.9400 | 1.0000 |
| CTIBench cti-ate 60 | 60 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 |
| own banks (dev, gold, Step 6) | 837 | 0.9845 | 0.9845 | 0.9845 | 0.9845 | 0.9845 | 0.9845 | 0.9892 | 0.9928 | 0.9964 | 0.9964 | 1.0000 |
| AttackQA weighted to 25,335 | 600 | 0.4954 | 0.4954 | 0.4954 | 0.4954 | 0.9355 | 0.9355 | 0.9355 | 0.9355 | 0.9355 | 0.9355 | 1.0000 |
| external retrieval (unweighted) | 564 | 0.6082 | 0.6082 | 0.6082 | 0.6082 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| AttackQA retrieval, weighted | 564 | 0.5296 | 0.5296 | 0.5296 | 0.5296 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

## AttackQA by family (sample n; stage shares)

| Family | n | stage shares |
|---|---|---|
| campaigns | 7 | outside 0.143, today 0.857 |
| groups | 15 | today 1.000 |
| relationships_campaigns_for_group | 5 | today 1.000 |
| relationships_campaigns_for_software | 6 | today 1.000 |
| relationships_campaigns_for_technique | 9 | today 1.000 |
| relationships_detections_summaries | 32 | outside 0.031, today 0.969 |
| relationships_detects | 53 | 4 0.566, outside 0.094, today 0.340 |
| relationships_groups_for_campaign | 5 | today 1.000 |
| relationships_groups_for_software | 14 | today 1.000 |
| relationships_groups_for_technique | 13 | today 1.000 |
| relationships_mitigations | 47 | 4 0.468, outside 0.298, today 0.234 |
| relationships_mitigations_summaries | 30 | 4 0.033, today 0.967 |
| relationships_software_for_campaign | 5 | today 1.000 |
| relationships_software_for_group | 7 | today 1.000 |
| relationships_software_for_technique | 13 | today 1.000 |
| relationships_techniques_for_campaign | 5 | today 1.000 |
| relationships_techniques_for_group | 8 | today 1.000 |
| relationships_techniques_for_software | 18 | today 1.000 |
| relationships_uses_software | 166 | 4 1.000 |
| software | 54 | 4 0.037, today 0.963 |
| tactics | 6 | outside 0.167, today 0.833 |
| techniques | 45 | outside 0.311, today 0.689 |
| techniques_parent | 13 | today 1.000 |
| techniques_sub | 7 | today 1.000 |
| techniques_tactics | 17 | today 1.000 |
