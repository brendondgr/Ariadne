# Issues — EXP-2026-08-010

Things that went wrong, or that a reader could reasonably object to. Recorded as
they were found, not tidied afterwards.

## I1 — cti-ate's own prompt is unusable, so its wording is not the wording asked

CTIBench poses `cti-ate` as a text-extraction task: a 3–8 KB instruction that
supplies the malware description **and appends the complete list of ATT&CK
technique identifiers as reference material**. Two problems, either fatal on its
own. It hands over the answer key. And it asks for extraction from prose, which
is not what Ariadne does — feeding it verbatim would measure a category
mismatch and report it as a system failure.

So cti-ate contributes its **item selection and its gold**, and the wording comes
from AttackQA's own template for the identical lookup ("What attack techniques
are used by software 'S0066: 3PARA RAT'?"). The phrasing is still external to
this repository, and using one benchmark's wording over the other's items is
what makes the two directly comparable.

**Why this matters to a reader:** the co-authorship control is intact on item
selection and on gold, which are the parts that decide the score. It is weaker
on phrasing, which was already the dimension this experiment could not fix
(see the Q16 limitation).

## I2 — the family-mapping test failed twice on its own anchors

`test_every_declared_family_resolves_against_the_real_graph` checks that each
question family resolves to a non-empty graph lookup. It failed twice, both
times because the anchor was badly chosen rather than because the mapping was
wrong: T1548 has six sub-techniques but no campaign uses it, and T1105 is used
by 29 campaigns but has no sub-techniques.

"Family returns nothing" reads as a broken mapping. It was not one. The reason
is recorded in the test itself so the next reader does not re-derive it.

## I3 — the ceiling was briefly routed through the arm runner

The first smoke test invoked `run_child` with `arm="oracle"`. There is no such
entry in `RUNNERS`, so all 182 items raised `KeyError` and were caught by the
per-item handler and written as empty answers — which score as a total
collapse, not as an error. The numbers were never reported, but the failure mode
is worth recording: **a caught exception that writes an empty answer is
indistinguishable from an arm that answered nothing.** `run_child` now refuses
`oracle` outright.

## I4 — scoring reads what was said, not what was found

An answer's claims carry `entity_ids` structurally. Those are excluded from the
primary metric, which reads only headline, narrative and claim text.

This is a choice, and it is the unfavourable one: this project already knows its
deterministic composer drops identifiers it retrieved, so counting `entity_ids`
would raise every deterministic figure. Both are computed and reported, and the
difference between them is a measurement rather than a footnote.

## I5 — the model-in-the-loop arms cover 60 of 182 questions

The local model answers one request at a time. Running the narrator and the
planner arms over all 182 items would take many hours. They run a fixed,
benchmark-balanced 60-item draw instead.

The fast arm is scored **twice** — once on all 182 and once on the same 60 — so
every comparison against a slow arm is a comparison of arms and not of sample
sizes. The 60-item cells carry correspondingly wider uncertainty and no
conclusion rests on a small difference between them.

## I6 — one CTIBench gold identifier is not in ATT&CK 19.0

Of the 292 gold identifiers attached to software this deployment holds, 291 are
present. One is not, so that item is excluded under D-021 rather than scored as
a miss. 14 further rows name software absent entirely — 13 Mobile, plus S0440,
retired between CTIBench's snapshot and ATT&CK 19.0.

## I7 — a "given" plan supplies less than the protocol assumed

The gold-replay path builds its `SubQuestion` from exactly six fields:
`id`, `source`, `text`, `entities`, `limits`, `join_key`. **`seed_ids` is not
among them.** The anchor identifier reaches the specialist only because it
appears in the question text.

Two consequences, and the second is the one that matters.

The co-authorship control is *stronger* than PROTOCOL.md section 3 claims: a
derived plan contributes `source: "attack"` and two entity labels, and nothing
else. The anchor is the benchmark's own wording.

And H4 is correspondingly **narrower** than it was pre-registered. The gap
between plan-given and plan-free is the value of a source name and two entity
labels — not of a fully specified plan. The hypothesis is reported against what
was actually measured, and the number must not be described as the value of
"being handed the plan" without that qualification.

This also holds for this project's own banks, whose entries carry `seed_ids`
that the deterministic arm never reads. Noted, not chased here.

## I8 — a false alarm, recorded because the reasoning was wrong twice

On seeing six question families score zero, the first probe compared entity
settings and appeared to show that the derived `entities` list caused the
collapse: `["Group","Software"]` returned 0 records, `[]` returned 1.

That probe was wrong in two ways at once. It used a placeholder question
("Question about G0003") rather than the benchmark's wording, so it measured
nothing the real run does. And the "1 record" it counted was the anchor node
itself, not a neighbour — an answer that finds the entity and none of its
relationships, scored as though it had found something.

Re-probed with the real question text, the derived entities make no difference:
the failing families fail with them, without them, and with them reversed. The
failures are the system's behaviour, not the harness's.

Recorded because "the control is contaminated" was the correct suspicion — it
was the same class of error as EXP-2026-08-009's confounded control — and
because the check that resolved it very nearly confirmed the wrong answer.

**I8 is itself partly wrong — see I9.** The entities list does matter. The
probes above never tried the setting that works, so they cleared the harness on
evidence that could not have convicted it.

## I9 — the derived plan was weaker than the one internal questions get

The suspicion in I8 was right after all, for a reason neither probe tested.

This project's own bank entries put the **relationship type** into `entities`
alongside the node labels. `H-SUB-01` carries
`["Technique", "SubTechnique", "HAS_SUBTECHNIQUE"]`. The derivation here supplied
only the two labels, on the reasoning that naming a relationship would be doing
the planner's job.

That reasoning was backwards. Withholding it does not make the control purer; it
makes the external plan **weaker than the internal one**, which converts a
harness deficit into an apparent system failure — the exact error this
experiment exists to avoid making about somebody else's benchmark.

Measured effect of appending the relationship type, three items per family:

| family | labels only | labels + relationship |
|---|---:|---:|
| techniques_sub | 0.000 | **1.000** |
| techniques_parent | 0.000 | **1.000** |
| software_for_group | 0.000 | 0.000 |
| groups_for_software | 0.000 | 0.000 |
| campaigns_for_software | 0.000 | 0.000 |
| software_for_campaign | 0.000 | 0.000 |
| techniques_for_group | 0.355 | 0.355 |
| techniques_for_software | 1.000 | 1.000 |

Two families were the harness. Four are unmoved by any planning hint and are a
real capability gap. One is partial and unmoved.

**Action taken.** The derivation now appends the relationship type. The run was
stopped and restarted rather than reported; the first run's numbers are
superseded and quoted nowhere.

**How this was found**, because the route matters. Internal `subtechnique_parent`
questions were checked against their committed answers, to test whether this
project's grader had been rewarding answers that omit the requested identifier.
It had not — the committed answers name `T1055` and `T1027` correctly. Reading
the bank entry to confirm that is what exposed the third element in `entities`.
The suspicion was wrong and checking it properly found the real defect anyway.

One intermediate check was also wrong and is worth naming: a substring test for
`"T1055"` matches inside `"T1055.002"`, and briefly suggested the internal
answers were passing on a technicality. The word-boundary extractor this
experiment already ships settled it.
