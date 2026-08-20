# What we changed today, and whether it worked

**Run started** 2026-08-19T23:29:56+00:00 · **phases** 14, 1 failed

Every number below was produced by the same grader in the same run, so the comparisons are like-for-like. Where a phase did not finish, it says so instead of showing a zero.

## 1. Did this morning's two fixes make answers better?

**What was broken.** The system was fetching the right information and then not saying it. Asked *"what is this technique and how does it work?"* it replied with internal bookkeeping — version numbers, deletion flags — while the actual explanation sat unused in the record it had just cited. Separately, when a record had a small set of related items, those items were fetched, checked, and then mentioned nowhere.

**How this was measured.** The same 30 questions as last night, graded by the same grader, compared **question by question**. Only the code changed between the two columns, so nothing else can explain a difference.

| | score out of 1.0 |
|---|---|
| before the fixes (last night) | 0.8367 |
| after the fixes | 0.9350 |
| **change** | **+0.0983** (95% confidence range +0.0250 to +0.1800) |

**10 questions got better, 2 got worse, 18 did not move.**

The confidence range stays above zero, which means the improvement is not an accident of which questions happened to be in the set.

The questions that actually moved:

| question | before | after | change |
|---|---:|---:|---:|
| `H-EXE-01` | 1.00 | 0.70 | -0.30 |
| `H-SUB-01` | 0.90 | 0.85 | -0.05 |
| `H-CHN-02` | 0.90 | 0.95 | +0.05 |
| `H-CTM-01` | 0.95 | 1.00 | +0.05 |
| `H-SW-01` | 0.90 | 0.95 | +0.05 |
| `H-CTM-02` | 0.90 | 1.00 | +0.10 |
| `H-CSQ-01` | 0.50 | 0.95 | +0.45 |
| `H-LKP-03` | 0.50 | 0.95 | +0.45 |
| `H-LKP-01` | 0.50 | 1.00 | +0.50 |
| `H-LKP-02` | 0.50 | 1.00 | +0.50 |
| `H-ABS-01` | 0.35 | 0.90 | +0.55 |
| `H-PRE-01` | 0.25 | 0.85 | +0.60 |

## 2. How do the four versions compare?

**The question set is new.** It was generated this morning, drawn to exclude every entity the old set used, and no version of the system has seen it. That matters: the old set had been used to find and fix bugs, which stops it being a fair test.

| version | questions | score | fully correct | made something up | declined, with proof |
|---|---:|---|---|---:|---|
| Normal system (pre-written query templates) | 30 | **0.9467** (0.915–0.972) | 29 of 30 | 0 | 4 of 4 |
| No templates (works the schema out at run time) | 30 | **0.9700** (0.940–0.992) | 29 of 30 | 2 | 4 of 4 |
| LLM-assisted (AI writes the prose answer) | 30 | **0.9773** (0.962–0.990) | 30 of 30 | 0 | 4 of 4 |
| AI writes the database query itself | 30 | **0.5000** (0.415–0.585) | 11 of 30 | 5 | 18 of 20 |

*"Made something up"* counts answers containing at least one statement the grader could not find in the retrieved evidence. *"Declined, with proof"* counts the times the system refused to answer **and** showed the query it ran to justify refusing — the behaviour the project leads with.

## 3. When the AI wrote its own queries, what went wrong?

This one needs care. Its score mixes two very different failures, and only one of them is the model's fault:

- it wrote a **bad query** — genuinely its own failure; or
- it wrote a **good query** whose results our own reader could not parse, because that reader was built around the column layouts the pre-written templates produce.

| outcome | questions | share |
|---|---:|---:|
| worked — query ran and produced evidence | 19 | 63% |
| **our reader's limitation** — query ran, output not understood | 7 | 23% |
| the database refused the query | 1 | 3% |
| the safety check refused every attempt | 3 | 10% |

**7 of 30 questions failed for a reason that is ours, not the model's.** Any comparison against the templated system has to say so. The honest reading is that the pre-written templates guarantee their own output is readable, which is a real advantage of that design — but it is a different advantage from writing better queries, and the two should not be reported as one number.

## 4. What ran

| phase | what it did | result | time |
|---|---|---|---:|
| `preflight` | graphs live, banks present, pre-fix judgments on disk | ok | 15s |
| `A1` | re-run the cascade on the OLD bank with the fixes in | ok | 1s |
| `A2` | grade it | ok | 189s |
| `A3` | pair it against last night, question by question | ok | 0s |
| `B-run-deterministic` | run deterministic on the fresh bank — the default cascade (templates) | ok | 1s |
| `B-judge-deterministic` | grade deterministic | ok | 272s |
| `B-run-generic` | run generic on the fresh bank — no templates — schema-derived primitives only | ok | 215s |
| `B-judge-generic` | grade generic | ok | 318s |
| `B-run-gold_loop_llm` | run gold_loop_llm on the fresh bank — authored plan + LLM narrator | ok | 162s |
| `B-judge-gold_loop_llm` | grade gold_loop_llm | ok | 158s |
| `B-run-llm_query` | run llm_query on the fresh bank — a language model writes the query itself | ok | 1008s |
| `B-judge-llm_query` | grade llm_query | ok | 165s |
| `C` | split the LLM-query failures by cause | ok | 0s |
| `D` | write the report | **None** | 0s |

**`D` failed:** `None`

## 5. Things that would make these numbers wrong

1. **The grader is a language model on the same server the system uses.** It agrees closely with the independent grader used earlier (correlation 0.93), but it is not independent, and it runs about 0.03 generous. Fine for comparing versions; not what you would publish an absolute score from.
2. **30 questions.** Small. A difference of a few hundredths is noise.
3. **The new question set was written by a language model**, from a prompt that shows it one entity and nothing about the system. That keeps it fair, but the phrasing is less varied than a human's would be.
4. **Each version answered each question once.** No repeat runs, so there is no estimate of how much a version varies with itself.

## 6. What is worth doing next

- **Decide how to report the AI-written-query comparison** — §3 is the whole question. Reporting the split is the honest option.
- **The merged-database test has infrastructure but no arm yet.** A second database container is set up and isolated; nothing has been loaded into it.
- **Re-grade with an independent model** before any of this leaves the repository.
- **28 commits are still local.** Nothing has been pushed.

