| arm | n | micro recall | micro precision | macro recall | exact |
|---|---:|---:|---:|---:|---:|
| ceiling (direct graph read) | 182 | 0.9863 | 0.8100 | 0.9853 | 0.7033 |
| deterministic, plan given | 182 | 0.6836 | 0.7701 | 0.6906 | 0.4451 |
| deterministic, plan given (subset of 60) | 60 | 0.7170 | 0.7815 | 0.7241 | 0.4833 |
| generic, plan given | 60 | 0.9953 | 0.8100 | 0.9822 | 0.7333 |
| LLM-planned, question text only | 60 | 0.6132 | 0.7670 | 0.6614 | 0.4500 |

| question family | n | ceiling | deterministic | shortfall |
|---|---:|---:|---:|---:|
| `relationships_campaigns_for_software` | 10 | 1.000 | 0.000 | -1.000 |
| `relationships_groups_for_software` | 10 | 1.000 | 0.000 | -1.000 |
| `relationships_software_for_campaign` | 10 | 1.000 | 0.000 | -1.000 |
| `relationships_software_for_group` | 10 | 1.000 | 0.000 | -1.000 |
| `relationships_techniques_for_group` | 10 | 0.990 | 0.295 | -0.694 |
| `relationships_techniques_for_campaign` | 10 | 0.988 | 0.326 | -0.661 |
| `relationships_campaigns_for_group` | 8 | 1.000 | 1.000 | +0.000 |
| `relationships_campaigns_for_technique` | 9 | 0.970 | 0.970 | +0.000 |
| `relationships_groups_for_campaign` | 10 | 1.000 | 1.000 | +0.000 |
| `relationships_groups_for_technique` | 10 | 0.983 | 0.983 | +0.000 |
| `relationships_software_for_technique` | 10 | 0.885 | 0.885 | +0.000 |
| `relationships_techniques_for_software` | 55 | 0.998 | 0.998 | +0.000 |
| `techniques_parent` | 10 | 1.000 | 1.000 | +0.000 |
| `techniques_sub` | 10 | 1.000 | 1.000 | +0.000 |

| benchmark | n | recall | precision | exact |
|---|---:|---:|---:|---:|
| attackqa | 137 | 0.5971 | 0.8778 | 0.3723 |
| cti-ate | 45 | 1.0000 | 0.6073 | 0.6667 |

