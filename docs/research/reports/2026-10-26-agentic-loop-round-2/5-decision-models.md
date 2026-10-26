# Decision Models for Grounding and Control in Ariadne: What the Evidence Supports

Decision models such as d3-lite should be used in Ariadne for the cheap, high-volume judgments (set membership, sufficiency pre-checks, ranking candidates). They should not be trusted on their own for the one decision that most damages accuracy, choosing the entity. For the entity, the evidence favours a staged design: graph-native filters first, a ranker second, a calibrated selector with an explicit "none" option third. Accept/ask/abstain thresholds can be calibrated automatically from synthetic, card-generated questions, but the resulting guarantee covers synthetic questions only, not real users.

## TL;DR

- **Where decision models fit:** d3-lite (0.85B, Apache-2.0, about 13.6 ms per text request on the vendor's GPU) is a good fit for batch set-membership and short yes/no gates. No published evidence shows that a sub-1B decision model can pick entities reliably from candidate lists in unseen domains. The closest head-to-head (LELA, on ZESHEL) shows entity-selection accuracy dropping steeply with model size: 83.1 at 24B, 76.8 at 30B-A3B, 68.0 at 4B. A reranker without LLM selection reaches only 27.2.\[1\] The proposal to make every classification a decision-model call should be narrowed. Question shape and plan validity are better decided structurally (typed requests plus executor diagnostics) than by a classifier.
- **Calibration without labels:** conformal "accept" guarantees need a labelled calibration set that is exchangeable with live traffic. A synthetic set generated from the source card can be built automatically (class B), but Ariadne's own paraphrase tiers (1.0 vs 0.0 records-exact) show that wording shifts the score distribution, which breaks exchangeability. Zhu et al. (arXiv 2608.01460) found that configuration shift "consistently erodes CP validity" across 9 LLMs, and synthetic-only calibration under-covers (SPI, arXiv 2505.13432). Treat synthetic-calibrated thresholds as a conservative starting point, measure the synthetic-to-real gap once on the existing ATT&CK/CAPEC/CWE banks, and monitor it online.
- **Cost of strict error targets:** no paper reports coverage-risk curves for entity linking or KGQA grounding at 10/5/1% wrong-entity rates; this is a genuine gap. The nearest evidence comes from conformal LLM judging (SCOPE; "Judge, Retrieve, or Abstain"). At α = 0.10 these keep 25-98% coverage.\[2\] At α = 0.05, coverage often collapses to 0-21%, unless extra evidence (retrieval) is added, which raised coverage from 0.07 to 0.82 in one setting.\[3\] Expect a 1% wrong-entity target to need graph-side evidence (types, neighbours, schema fit) and an "ask" band, not a better threshold alone.

## Key Findings

1. **No decision model has been evaluated on KG grounding.** d3-lite's card reports a general "Jev Decision Index" (public suite 36.93) and latency, but no entity, relation or schema-selection results and no calibration results [READ].\[4\]\[5\] The brief's own measurement (right relation at p = 0.614, right entity at p = 0.791) is the only grounding evidence that exists for it. If those figures are mean probabilities on the gold option, the model is uncertain on roughly one in three relation decisions, and a threshold will push many of them into "ask".
2. **On grounding, generative selection beats pointwise scoring, and scale matters a great deal.** In LELA [READ], a training-free pipeline (retrieve → Qwen3-Reranker-4B → LLM selects from 10 candidates) on ZESHEL gives:\[6\]
   - normalized accuracy of 83.11 with Magistral-Small-2509 (24B), 76.79 with Qwen3-30B-A3B and 68.00 with Qwen3-4B;
   - 27.15 for the reranker alone with no LLM selection;
   - 74.27 for the BLINK cross-encoder used "true zero-shot" (trained once, never on the target).\[1\]\[6\]
   Turning reasoning off cut Qwen3-30B-A3B from 76.79 to 54.23 and Qwen3-4B from 68.00 to 40.14.\[1\] This is the strongest head-to-head evidence that a small model with no generated text (d3-lite's operating mode) is the wrong tool for the hardest entity picks. A 27-35B model with thinking on is the right tool, at a cost.
3. **"None of these" is the weak point everywhere.** On ESCO, where 813 of 1,824 test mentions have no correct entity, LELA's "UNK" accuracy was only 5.41 (Magistral), 28.04 (Qwen3-30B-A3B) and 8.36 (Qwen3-4B) [READ].\[1\] LLM selectors strongly prefer picking something. This matches Ariadne's own finding that an LLM picked the wrong entity 35% of the time. NIL detection must therefore be built from signals other than the selector's own choice.
4. **Training-free retrieval plus an LLM selector is competitive with trained linkers on general-domain data.** In "Select, Don't Train" [READ, partial: abstract and methods], BM25 plus an LLM selector raised ZELDA in-KB micro-F1 from 82.3 to 86.3. A trained dense retriever raised it to 88.5. Abstention-aware scoring reached 90.7 F1. The selectors were Qwen3-32B, Mistral-Small-24B and two GPT minis.\[7\] The model class Ariadne plans to run locally is therefore the one the evidence supports for entity choice.
5. **Out-of-the-box calibration does not transfer reliably across domains, and temperature scaling can make it worse.** Temperature scaling fitted on one domain worsened conf-ECE on LLaMA out of domain from 0.1784 to 0.2513 [SNIPPET, arXiv 2608.07419].\[8\] Earlier work on BERT/RoBERTa found temperature scaling good in domain but label smoothing better out of domain [SNIPPET, arXiv 2003.07892].\[9\] A clinical extraction study found the direction of miscalibration reverses across domains (underconfident on one, overconfident on the other) [ABSTRACT, arXiv 2603.00924].\[10\] Calibration must be done per graph and per decision type.
6. **Conformal risk control works with roughly 1,000 labels, but its guarantee is only as good as exchangeability.** COIN, SCOPE and "Judge, Retrieve, or Abstain" all held the error among accepted answers at or below target, using about 1,000 calibration items [READ by delegated reader].\[11\]\[12\]\[13\] A naive threshold without finite-sample correction overshot: 0.116-0.124 against a 0.10 target in SCOPE.\[2\] Zhu et al. (arXiv 2608.01460, accepted to EMNLP 2026 main) tested 9 LLMs, 4 datasets and 4 nonconformity scores under changes in prompt template, decoding temperature and weight quantization between calibration and test. They found that such configuration shift "consistently erodes CP validity, often driving empirical coverage below the target" [SNIPPET].
7. **No published model has been trained across many KGs for question grounding and tested on unseen KGs.** This is an open research question. The nearest analogues are:
   - cross-database text-to-SQL schema linkers (trained once on Spider/BIRD, applied to unseen databases);\[14\]
   - ZESHEL-style zero-shot entity linking (trained on 8 Wikia domains, tested on 4 unseen ones);\[15\]
   - KG foundation models (ULTRA, KG-ICL). These transfer link prediction, not question grounding, and use graph structure rather than text.\[16\]\[17\]
8. **Batch set membership is where decision models pay off.** d3-lite serves 518 requests/s on one AMD MI325X with batching [READ].\[5\] "The Embedder's Dilemma" (El Assadi, Muennighoff and Lee, arXiv 2608.12875) says in its abstract that open LLMs "process tokens 2.5 to 736x more slowly on the same GPU" than embedding models. Its body text, seen only as a snippet and unverified, puts local 27-35B LLMs under vLLM at about 5,400-5,900 tokens/s on an H100. Judging 10,000 items of about 200 tokens each therefore takes on the order of 20 s with d3-lite and roughly 6 minutes of prefill alone with the controller model (my arithmetic from those figures).
9. **Graph content is untrusted text, and every model class here can be steered by it.** Content-injection attacks fool retrievers, cross-encoder rerankers and LLM judges [SNIPPET, arXiv 2501.18536].\[18\] In LLM rankers, injected instructions can raise a target document's rank [SNIPPET, arXiv 2602.16752].\[19\] Option-position bias is strongest in small models: in LELA, shuffling candidates cost Qwen3-4B 4.84 points against Magistral's under 0.4 [READ].\[1\]

## Comparison Table

Class key: P = plug-and-play off the shelf; B = automatic one-time build per graph; T = training on target graph/task. "Trained once" models used unchanged on a new graph count as P, with an explicit domain-shift risk.

| Model / method | Output | Size | Latency / throughput | Class | Best grounding evidence | Calibration evidence | Read status |
|---|---|---|---|---|---|---|---|
| d3-lite (vLLM-SR Decision 3.0) | Probability per option for choice / yes-no / score; no text | 0.85B (0.10B vision); Apache-2.0 | 13.6 ms median text (MI325X, one at a time); 518 req/s batched; Ariadne measured ~80 ms | P | None published. Ariadne: gold relation p = 0.614, gold entity p = 0.791 | None published | Card [READ]\[5\] |
| LLM as classifier via label log-probs (e.g., local 27-35B) | Softmax over option tokens | 27-35B | 0.30-0.41 s per 4-option pick (Ariadne measurement) | P | LELA-style selection with reasoning: 76.8-83.1 ZESHEL; without reasoning much lower | Option-token priors cause selection bias (PriDe); temperature scaling fragile out of domain | LELA [READ]; PriDe [ABSTRACT] |
| Generative LLM selector with reasoning + self-consistency | Chosen index (vote share usable as confidence) | 4-32B | LELA: 11.7-44.4 s per mention with 3-10 samples | P | ZESHEL 83.11 (24B); ZELDA 86.3 F1 with BM25 (Select, Don't Train) | Vote share: about 60% of mentions unanimous over 10 samples (LELA)\[1\] | LELA [READ]; RAISED [READ, partial] |
| Pointwise LLM reranker (Qwen3-Reranker-0.6B/4B) | P(yes) per (query, candidate) | 0.6B / 4B | Not measured here | P | Recall@10 93.57 on ZESHEL, but top-1 alone 27.15\[1\] | None found | LELA [READ] |
| Cross-encoder reranker (bge-reranker-v2-m3) | Relevance score | 568M; Apache-2.0 | ~40-110 ms p50 per query batch on L4 (vendor benchmark) | P | No EL/KG result found | None found | [SNIPPET]\[20\] |
| BLINK (bi-encoder + cross-encoder) | Dense retrieval score; reranker score | BERT-large-based | Bi-encoder: 5.9M candidates in 2 ms | P (Wikipedia-trained); T to adapt | ZESHEL true zero-shot 74.27; TACKBP-2010 92.9 bi-encoder vs 94.5 full | None found | LELA table [READ]; BLINK [SNIPPET]\[21\] |
| ReFinED | Mention spans, types, entity scores | Transformer, single pass | "More than 60 times faster" than competing approaches | P (new entities added via descriptions) | +3.7 F1 average on standard EL sets | Not reported | [ABSTRACT]\[22\] |
| GenDecider (LoRA-tuned LLM reranker with "none") | Choice incl. "none of the candidates" | LLM + LoRA | n/a | T (trained on ZESHEL) | ZESHEL 82.75\[1\] | n/a | Via LELA [READ] |
| NLI zero-shot classifiers | Entailment probability per label | ~0.4B | n/a | P | Not searched this round | Not searched | No evidence gathered |
| Reward / verifier / small judge models | Scalar score or verdict | 1-70B | n/a | P | Conformal judging: see SCOPE, JRA | SCOPE ECE 0.062-0.174 for its score vs 0.092-0.239 raw | [READ by delegated reader]\[2\] |
| Cross-DB schema linkers (RESDSQL cross-encoder, ExSL, AttnLink) | Probability per table/column | ~0.3-7B | AttnLink: single prefill pass, "millisecond-scale" | T once, then P on unseen DBs | RESDSQL table AUC 0.9973; AttnLink transfers BIRD→Spider2 | Probability-based, so recall/precision tunable | [SNIPPET]\[14\]\[23\] |
| ULTRA / KG-ICL | Link-prediction scores | ULTRA <200k params | n/a | P on new KGs (pre-trained on 3-several KGs) | ULTRA zero-shot "often on par or better than strong baselines trained on specific graphs" across 57 KGs (Galkin et al., ICLR 2024) | n/a | [SNIPPET] |
| Embedding filter (BGE-M3 etc.) | Cosine similarity | 0.1-14B | 640K tok/s BGE-M3 on H100 | P (index build is B) | Qwen3-Embedding-4B put gold at rank 1 in >60% of ZESHEL cases\[1\] | Similarities are not probabilities | Embedder's Dilemma [SNIPPET]; LELA [READ]\[24\] |

## Details

### Q1. What exists, and how to read it

- **d3-lite** is a classification head over Qwen3.5-0.8B. It answers several choice, yes/no and score questions about one input in one call, each "from its own forward pass", and returns a probability for every option [READ].\[5\] Its strengths are predictable latency and no parsing failures. Its weakness for Ariadne is that it was trained for routing-style decisions ("which team handles this request"). Its card claims nothing about reading long entity descriptions or abstaining, and nothing about calibration. One detail matters for thresholds: with batching turned on, "a few near-tie decisions change" [READ].\[5\] Near-tie cases are exactly the ones an ask band exists for, so thresholds must be fitted with the same serving mode used in production.
- **LLM-as-classifier via label log-probabilities** means reading the probability the model assigns to each option token ("A", "B", ...) rather than letting it write text. It costs one forward pass. Its known flaw is selection bias: models put prior mass on particular option-ID tokens. PriDe (ICLR 2024) estimates and removes this prior using permutations of a few samples, label-free [ABSTRACT].\[25\]\[26\]
- **Bi-encoder vs cross-encoder.** A bi-encoder embeds the question and each candidate separately and compares the vectors. It is fast because candidate vectors are precomputed, but it cannot compare the two texts word by word. A cross-encoder reads question and candidate together in one pass. It is more accurate but must run once per pair. BLINK uses a bi-encoder for retrieval and a cross-encoder to rerank. Its bi-encoder links against 5.9M candidates in 2 ms [SNIPPET].\[21\]\[27\]
- **Entity linkers trained once** (BLINK, ReFinED) carry over to new entity sets because they score entity descriptions and types, not memorised IDs. ReFinED adds new entities "without retraining" [SNIPPET, GitHub README].\[28\] Both were trained on Wikipedia, so ATT&CK-style descriptions are a domain shift.

### Q2. Accuracy on grounding tasks: head-to-head evidence

- **Entity selection from a candidate list with descriptions.** The best controlled comparison is LELA's ZESHEL table [READ], which uses the same candidates and descriptions throughout:\[1\]

| System | Training on target? | ZESHEL macro normalized acc. |
|---|---|---|
| GenDecider (LoRA LLM) | Trained on ZESHEL train domains | 82.75 |
| BLINK cross-encoder | Trained on train domains | 77.15\[1\]\[6\] |
| BLINK, true zero-shot | No | 74.27\[6\] |
| LELA + Magistral-Small-2509 (24B) | No | 83.11 |
| LELA + Qwen3-30B-A3B | No | 76.79 |
| LELA + Qwen3-4B | No | 68.00 |
| Reranker only (Qwen3-Reranker-4B) | No | 27.15 |

What this means for Ariadne: a generative pick by a 24-35B model with reasoning matches trained linkers. A trained-once cross-encoder (BLINK) is about 9 points behind. Pointwise scoring alone is far behind on top-1, even though it keeps 93.57% of golds in the top 10. A pointwise model is a good filter and a poor final judge. d3-lite answering "is this the entity?" per candidate is pointwise scoring.

- **Relation / schema-item selection given glosses.** No KGQA study compares a small decision model with an LLM pick on relation selection. Text-to-SQL schema linking is the closest field. There, trained cross-encoders (RESDSQL) reach table-ranking AUC 0.9973 [SNIPPET].\[23\] An EDBT 2026 analysis found recall matters more than precision for downstream success, and that a small code model (DeepSeek-Coder-6.7B) was "quite competitive and in some cases the strongest" schema linker [SNIPPET].\[29\] Ariadne's case is easier than text-to-SQL in one way: the source card limits relations to the allowed (source label, relation, target label) patterns for the anchor's label, so the menu is usually small. A typed menu of 3-10 valid relations is exactly where choosing from a list beats free generation.
- **NIL detection.** Evidence is consistently weak:
  - LLM selectors under-predict NIL (LELA on ESCO: 5-28% UNK accuracy, against 44.57% for an always-UNK baseline) [READ].\[1\]
  - Cross-encoders trained with cross-entropy "fail to assign low scores to NIL mentions", because cross-entropy only teaches relative ranking [SNIPPET, arXiv 2301.13318].\[30\]
  - Adding a learned [NIL] candidate to BLINK (BLINKout) improved out-of-KB detection [SNIPPET].\[31\]
  - Abstention-aware selection lifted RAISED to 90.7 F1 [READ, partial].\[7\]
  - Conclusion: "none" must be an explicit option and also a separate, graph-informed check. The selector's argmax alone is not enough.

### Q3. Calibration

**Terms.**
- *Calibration*: a model is calibrated if, among all answers given with confidence 0.8, about 80% are right.
- *Expected calibration error (ECE)*: sort predictions into confidence bins (usually 10) and take the weighted average gap between mean confidence and accuracy in each bin: ECE = Σ_b (|B_b|/N)·|acc(B_b) − conf(B_b)|.\[2\]\[32\]
- *Temperature scaling*: divide the logits by one fitted number T before the softmax. It changes confidence without changing which option wins.\[33\]
- *Isotonic regression*: fits a free-form non-decreasing map from score to probability. It is more flexible but needs more labels (typically hundreds to thousands per decision type; I found no NLP-specific label-count study this round).
- *Conformal prediction*: uses a held-out labelled set to pick a score threshold with a finite-sample guarantee. For selective decisions, *conformal risk control* picks the lowest threshold λ whose upper confidence bound on the error among accepted items is at most α.\[12\]\[13\] Example: "among accepted entity links, at most 5% are wrong, with probability 95% over the draw of the calibration set."\[11\]

**Out-of-the-box calibration on unseen domains.** No calibration figures exist for d3-lite, Qwen3-Reranker or bge-reranker on any KG task. General findings:
- Temperature fitted in one domain can raise ECE elsewhere (0.1784 → 0.2513) [SNIPPET].\[8\]
- Miscalibration direction can flip between domains [ABSTRACT].\[10\]
- Thermometer (ICML 2024) predicts a temperature for an unlabelled new dataset, a label-free option worth noting [SNIPPET].\[33\]
- Raw max-probability is a poor ranking signal for abstention. A preprint reports softmax-score rejection reaching under 7.5% coverage at 1% risk in VQA [SNIPPET, cited in arXiv 2609.27225; not an EL result].\[34\]

**How many labels.**
- *Conformal risk control*: COIN calibrated on about 1,000 TriviaQA items and about 5,478 CommonsenseQA items. With about 200 calibration items (1:9 split), risk stayed controlled on average but with higher variance. With about 109 items (MMVet) the method still ran [READ by delegated reader].\[11\]
- *SCOPE and "Judge, Retrieve, or Abstain"*: about 1,000 calibration items each [READ by delegated reader].\[2\]\[3\]
- *Synthetic-Powered Predictive Inference (SPI)*: split conformal needs at least 19 points at α = 0.05 for a non-trivial set at all [READ by delegated reader].\[35\]
- *A useful rule of thumb (my calculation, not from a paper)*: if a threshold accepts n calibration items with zero errors, the one-sided 95% upper bound on error is about 3/n (the "rule of three"). Certifying 10% needs about 30 accepted, error-free items, 5% about 60, and 1% about 300, and more if any errors occur. A 1% wrong-entity guarantee per graph therefore needs a calibration set in the high hundreds or more, so it is only feasible if the set is generated automatically.

**The central tension: no hand labels, but conformal needs labels.**
1. *Can calibration sets be generated automatically from each graph?* Yes, and the generator is class B. Sample anchor nodes and allowed (label, relation, label) patterns from the source card. Have the local LLM write questions at each paraphrase tier (identifier, name, paraphrased name, description only, synonym verb). The gold entity and relation are known by construction, and the gold records come from executing the typed request. SynthKGQA built 30,477 training questions from Wikidata with GPT-4.1, validated by executable queries, and reports that retrievers trained on it "transfer well to human-curated KGQA datasets" [SNIPPET, arXiv 2511.04473].\[36\] Sidiropoulos et al. generated questions for unseen KG domains for relation prediction. The gap between synthetic and gold training questions was small below 100 questions and widened as data grew [SNIPPET, arXiv 2005.12040].\[37\]
2. *Does synthetic calibration transfer to real users?* There is no direct evidence for KGQA, and I disagree with any plan that treats it as transferring. The conformal guarantee requires calibration and test examples to be exchangeable, meaning drawn from the same distribution.\[38\]\[39\] LLM-written questions are a different distribution from user questions, and Ariadne's own tiers show how much wording moves scores (records-exact 1.0 → 0.0). The closest results:
   - SPI: synthetic-only calibration "fails to achieve the target coverage level... due to distribution shift between the real and synthetic data" [READ by delegated reader].\[35\]\[40\]
   - Configuration shift drives coverage below target, and "gathering more calibration data deepens the bias" [SNIPPET, arXiv 2608.01460].\[41\]
   - "Conformity Breaks Conformal": coverage fell from 90% to 74% under an endogenous shift [SNIPPET, arXiv 2609.04445].\[42\]
   - One encouraging result: in "Judge, Retrieve, or Abstain", re-fetching web evidence three months later (top-3 URL overlap only 0.24-0.30) still kept error at or below target, with coverage moving by at most 0.06 [READ by delegated reader].\[3\] Some shifts are benign. Whether Ariadne's is benign has to be measured.
3. *What to do instead*:
   - (a) Generate the synthetic calibration set to be harder than real traffic: over-sample description-only and paraphrased-name tiers and near-duplicate distractors (same label, similar names). Thresholds fitted there are conservative if real questions are easier on average. This is an assumption to test, not a guarantee.
   - (b) Use SPI-style combination: a few real labelled items plus many synthetic ones. Bashari, Lotan, Lee, Dobriban and Romano (arXiv 2505.13432) show that SPI "provably achieves finite-sample coverage guarantees without making any assumptions about the real and synthetic data distributions", although their experiments cover only image classification and tabular regression, not NLP [READ by delegated reader]. The "real" items can come from the existing sealed banks on the three current graphs, used once for research validation, not per graph.
   - (c) Harvest weak labels online from the executor. An empty result, a schema-incompatible expansion, or a validator failure is a strong signal that grounding was wrong. Online conformal abstention under partial feedback exists in the literature (ExAUL) [SNIPPET, arXiv 2506.14067].\[43\]
   - (d) Report every guarantee as "valid for the synthetic distribution", and publish the measured synthetic-to-real gap.

### Q4. Selective prediction: coverage given up for 10%, 5%, 1% wrong-entity rates

**Terms.** *Coverage* is the fraction of questions the system answers without asking or abstaining. *Selective risk* is the error rate among answered ones.\[44\] A *coverage-risk curve* plots risk against coverage as the threshold moves; the area under it (AURC) summarises the trade-off.\[45\]

**Evidence.** I found no paper reporting coverage at 90/95/99% precision for entity linking or KGQA grounding. The delegated search confirmed this gap. The best available proxies are conformal LLM-judging results [READ by delegated reader]:
- SCOPE, α = 0.10: coverage 0.246-0.983 depending on model and benchmark.\[2\]
- SCOPE, MT-Bench at α = 0.05: coverage 0.018 (Qwen-7B) and 0.072 (Llama-70B).\[2\]
- "Judge, Retrieve, or Abstain", α = 0.05: most configurations 0.00-0.21. Adding retrieved evidence at α = 0.20 lifted NQ-Open coverage from 0.07 to 0.82.\[3\]

**Interpretation for Ariadne.** At a 10% wrong-entity target, expect to keep a usable majority of questions. At 5%, expect a sharp drop unless the confidence score improves. At 1%, a probability threshold alone will probably give near-zero coverage on the name/paraphrase/description tiers. The lever is better evidence, not tighter thresholds:
- a schema-compatibility filter (the candidate's label must take part in a pattern the question needs);
- neighbourhood agreement (does the candidate have the relation the question asks about?);
- agreement between independent scorers (embedding rank, LLM pick, d3-lite yes/no).
This mirrors retrieval raising coverage in the judging study. Ariadne's existing asymmetry also helps: the planner never retrieved records where the correct plan retrieved none, so emptiness is a reliable failure signal.

### Q5. Trained once, used on unseen graphs

- **Status: open.** I found no schema-conditioned grounding model trained across many KGs on synthetic questions and tested on held-out KGs for entity/relation grounding.
- **Nearest work.**
  - *Zero-shot EL (ZESHEL)*: train on 8 Wikia worlds, test on 4 unseen ones, using descriptions only.\[15\] Trained cross-encoders reach about 77-83 normalized accuracy [READ via LELA].\[1\]
  - *Cross-database text-to-SQL schema linking*: trained once, applied to unseen schemas. AttnLink's BIRD-trained linker "still performs strongly" on Spider2-SQLite, which has no training split [SNIPPET].\[14\]
  - *KG foundation models*: ULTRA was pre-trained on 3 KGs and evaluated zero-shot on 57. Galkin et al. (ICLR 2024) report that its zero-shot performance "is often on par or better than strong baselines trained on specific graphs". Gains saturate after about 4 pre-training graphs, and diversity of relational patterns matters more than size [SNIPPET]. KG-ICL covers 43 KGs (6-layer pre-trained average MRR 0.443) [SNIPPET].\[46\] Both do structural link prediction and ignore text (SEMMA adds relation-name semantics [SNIPPET]), so they cannot read a question.\[47\] Their transferable ingredient is the idea of representing relations by how they interact rather than by name.
- **What training data a cross-graph grounder would need.** By analogy with ZESHEL (8 training worlds out of 16 Wikias, with 49,275 labelled training mentions per Logeswaran et al. 2019, arXiv 1906.07348) and ULTRA (saturation at 4+ graphs): tens of diverse graphs with tens of thousands of synthetic (question, card, candidates, gold) tuples, with near-miss negatives drawn from the same label. Wikidata subsets, open security KGs and LLM-extracted document graphs could provide them. Treat these numbers as an informed estimate, not evidence.
- **Experiment design.** Leave-one-graph-out:
  - Train a cross-encoder or small LLM on synthetic tuples from N graphs (vary N from 3 to 20) and test on the held-out graph's real paraphrase-tier bank.
  - Compare against (i) the zero-shot 27-35B selector and (ii) d3-lite.
  - Decide on wrong-entity rate at fixed 80% coverage and on ECE on the held-out graph.
  - If the trained model beats the zero-shot selector on held-out graphs at under 1/10 the latency, the plug-and-play constraint is met with one training run, not per-graph training.

### Q6. Batch classification over 100-10,000 items

| Approach | Throughput basis | 10,000 items × ~200 tokens | Accuracy evidence |
|---|---|---|---|
| Embedding filter | BGE-M3 ≈ 640K tok/s on H100 [SNIPPET] | ~3 s (my arithmetic) | Good for recall; similarity is not a judgment\[24\] |
| d3-lite yes/no | 518 req/s batched on MI325X [READ] | ~20 s | No published accuracy on topical judgments like "concerns cloud identity"\[5\] |
| Local 27-35B LLM, one label token | Open LLMs "2.5 to 736x more slowly" than embedders (Embedder's Dilemma abstract); ~5,400-5,900 tok/s on H100 in its body [SNIPPET, unverified] | ~6 min | Generally strongest; fine-tuned encoders beat prompted LLMs on fixed-label tasks at $7-11 vs $463-2,702 per 1M requests [SNIPPET, arXiv 2602.06370] |

**Recommended pattern.**
1. The database computes the candidate set.
2. An embedding pass ranks it.
3. d3-lite judges every member.
4. The controller LLM re-judges only the uncertain band and a random audit sample.
5. Membership appears in the answer only through the deterministic composer, together with the judgment's probability.
Nothing is dropped by step 2, which orders items and never removes them. This respects the envelope rule.

### Q7. Failure modes

- **Position and option-ID bias.** Comes mainly from token priors on option IDs; PriDe reduces it label-free [ABSTRACT].\[25\]\[48\] In LELA, Qwen3-4B lost 4.84 points under shuffling, while Magistral lost almost nothing [READ]. Placing "None" first vs last had only marginal effects [READ].\[1\] Mitigation: present options in reranker order, and for d3-lite average over 2-3 permutations on near-ties.
- **Wording sensitivity.** Ariadne's tier results are the strongest evidence here. Every decision model must be evaluated per tier, not on pooled accuracy.
- **Long-description truncation.** LELA's selection accuracy fell as input length grew, and fell most steeply for the MoE model [READ]. A cap of 8,192 tokens cost accuracy (Magistral 83.11 → 77.73 in the "opt" configuration, which also cut self-consistency samples) [READ].\[1\]\[6\] Mitigation: build-time (class B) short glosses per node, with the full description fetched only for the top 2-3.
- **Adversarial or misleading descriptions.** Injected text can promote a candidate in rerankers and LLM judges [SNIPPET].\[18\]\[19\] LLM-extracted graphs are especially exposed. Mitigations:
  - never let description text alone decide identity; require structural agreement (label, identifier scheme, neighbourhood);
  - strip instruction-like spans from descriptions at build time;
  - route high-impact accepts (an entity that changes the answer set) through the ask band when only text supports them.

### Evidence status by source

| Source | Venue / type | Read status |
|---|---|---|
| d3-lite model card (vllm-sr/d3-lite, Hugging Face) | Vendor model card | [READ] |
| LELA, Haffoudhi, Suchanek, Holzenberger, arXiv 2601.05192\[1\] | Preprint | [READ] |
| Select, Don't Train (RAISED), Polat et al., arXiv 2608.27470 | Preprint | [READ, partial] |
| COIN, arXiv 2506.20178 | Preprint | [READ by delegated reader]\[49\] |
| SCOPE, arXiv 2602.13110 | ICML 2026 (peer-reviewed) | [READ by delegated reader]\[50\] |
| Judge, Retrieve, or Abstain, arXiv 2608.17994 | Preprint | [READ by delegated reader]\[51\] |
| Synthetic-Powered Predictive Inference, arXiv 2505.13432 | Preprint | [READ by delegated reader]\[52\] |
| ReFinED, NAACL 2022 Industry | Peer-reviewed | [ABSTRACT] |
| BLINK, EMNLP 2020 | Peer-reviewed | [SNIPPET] |
| PriDe, ICLR 2024 | Peer-reviewed | [ABSTRACT] |
| ULTRA (ICLR 2024); KG-ICL (NeurIPS 2024) | Peer-reviewed | [SNIPPET] |
| SynthKGQA/GTSQA, arXiv 2511.04473 | Preprint | [SNIPPET] |
| Sidiropoulos et al., arXiv 2005.12040 | Preprint | [SNIPPET] |
| Bilevel LLM calibration, arXiv 2608.07419; Desai & Durrett, arXiv 2003.07892 | Preprint; EMNLP 2020 | [SNIPPET] |
| Conformalized LLMs under configuration shift, arXiv 2608.01460 | Preprint | [SNIPPET] |
| Conformity Breaks Conformal, arXiv 2609.04445 | Preprint | [SNIPPET] |
| Embedder's Dilemma, arXiv 2608.12875 | Preprint | [SNIPPET] |
| Illusions of Relevance, arXiv 2501.18536; LLM ranker injection, arXiv 2602.16752 | Preprints | [SNIPPET] |
| RESDSQL (AAAI 2023); AttnLink, arXiv 2608.00693; EDBT 2026 schema-linking analysis | Mixed | [SNIPPET] |
| Proxy-based zero-shot EL, arXiv 2301.13318; BLINKout, arXiv 2302.07189 | Preprints | [SNIPPET] |

## Recommendations: one per decision in the loop

Threshold scheme used throughout:
- **Accept** if the calibrated score is at least λ_accept. λ_accept is the lowest threshold whose Clopper-Pearson 95% upper bound on error among accepted synthetic calibration items is at most α. This is the bound COIN uses (Wang et al., arXiv 2506.20178), which "applies confidence interval methods such as Clopper-Pearson to establish a high-probability upper bound on the true error rate (i.e., FDR)".
- **Abstain** if the "none"/NIL probability exceeds its own conformal threshold, or if the score falls below λ_low (set where selective risk on the calibration set exceeds 50%).
- **Ask** in between, or whenever the top-2 margin is below a fitted margin threshold.
- Fit everything per graph and per decision type, using the production serving mode.

1. **Entity (highest priority; wrong entities pass the claim verifier).**
   - Pipeline: deterministic exact/identifier match first. Then candidate retrieval (BM25 + embeddings over names and build-time glosses), then the schema-compatibility filter (class B, computed from the card), then an explicit "None of these" option. The local 27-35B controller selects with thinking on from at most 10 options in reranker order, using 3 self-consistency samples. d3-lite yes/no on the chosen candidate serves as an independent second opinion.
   - Confidence score: the joint signal of self-consistency vote share, d3-lite probability and structural agreement.
   - Calibration: conformal risk control on synthetic tier-stratified questions (class B), α = 0.05 to start.
   - Ask whenever two candidates survive the filter with close scores. Under the embedding contract, "ask" returns the candidate list to the calling system.
   - Expect roughly 15-45 s per hard entity if LELA's runtimes carry over. Use this only on the slow path.
2. **Relation.** A d3-lite choice over the card-computed valid menu (usually small), with the controller LLM as fallback below λ_accept. Calibrate on synthetic questions per relation pattern. Prefer recall: if two relations tie, execute both. They are cheap deterministic calls, and the executor's results decide. This follows the schema-linking finding that recall dominates.\[29\]\[53\]
3. **Question shape.** Do not use a classifier as the authority. Shape (lookup, enumerate, count, chain, compare, aggregate) should follow from the typed request the controller builds and from executor feedback. A d3-lite shape guess is acceptable only as a fast-path router, with no threshold guarantee, because a wrong route fails visibly and falls back.
4. **Plan check.** Use structural validation (schema-valid, bounded, types line up) plus executor diagnostics, as the earlier rounds settled. A decision model adds little here, because a plan "answering the question" cannot be judged better than by running it. If one is used, make it an advisory d3-lite yes/no with no accept power.
5. **Sufficiency ("do these records answer it?").** d3-lite yes/no over the envelope (totals, facets, labelled sample) as a cheap pre-check before drafting. The validator keeps the final say, and so does the stopping decision. Calibrate against synthetic questions whose gold records are known (sufficient means gold records ⊆ retrieved). Set α loose (0.10), because a false "sufficient" is caught by the validator. A false "insufficient" only costs another loop turn.
6. **Set membership (judgments the database cannot compute).** d3-lite per item, embedding ranking for ordering only, and controller re-judgment for the ask band plus a 2-5% random audit. Calibrate with LLM-labelled audit samples (the controller as teacher). This gives a guarantee relative to the controller, not to the truth, and must be reported as such. Output every item with its probability and band. Never silently drop members.

## Experiments on Ariadne's paraphrase-tier banks

1. **Entity selector bake-off at fixed coverage.**
   - Arms: d3-lite, Qwen3-Reranker-0.6B top-1, bge-reranker-v2-m3 top-1, controller with thinking on and off, controller + d3-lite agreement. All arms run behind the same schema-compatibility filter and "none" option.
   - Deciding measurement: wrong-entity rate at 80% and 60% coverage, per tier (name, paraphrased name, description-only), plus median latency.
   - Decision rule: adopt the cheapest arm within 2 points of the best.
2. **Synthetic-to-real calibration transfer.**
   - Generate a tier-stratified synthetic set from the ATT&CK/CAPEC/CWE cards (class B) and fit conformal thresholds at α = 0.10 and 0.05. Apply them unchanged to the sealed real banks.
   - Deciding measurement: realised wrong-entity rate among accepted items on real questions vs α, ECE on real vs synthetic, and coverage.
   - If the realised error exceeds α + 0.02, synthetic calibration is not trustworthy alone; adopt SPI-style mixing or the "harder than real" generator and re-test.
3. **NIL robustness.**
   - Remove the gold entity from the candidate list for half of each tier.
   - Deciding measurement: confident-wrong rate (accepted with gold absent) and false-NIL rate (abstained with gold present), comparing the selector's "none" option, d3-lite "none of these", and a structural NIL rule (no candidate has the required relation).
   - This directly targets the rewrite-stage failure that doubled confident-wrong answers.
4. **Position and injection stress.**
   - Shuffle candidate order across 3 permutations, and inject instruction-like text into distractor descriptions in an LLM-extracted test graph.
   - Deciding measurement: flip rate of accepted decisions and wrong-entity rate under injection, for d3-lite vs the controller.
   - Pass criterion: flip rate below 2% among accepted decisions.
5. **Batch membership throughput and agreement.**
   - On 100 / 1,000 / 10,000-member sets from ATT&CK (e.g., techniques "concerning cloud identity"), compare d3-lite, embedding threshold, and controller map-reduce.
   - Deciding measurement: wall-clock on the single local GPU, and agreement (Cohen's κ) with controller labels on a 300-item audit.
   - Adopt d3-lite if κ ≥ 0.8 at under 1/10 the controller's time.

## Caveats

- Several key figures (calibration transfer, configuration shift, KG foundation models, throughput) are [SNIPPET] or [ABSTRACT] leads. They indicate direction, not measured facts about Ariadne's setting.
- COIN, SCOPE, JRA and SPI figures were read in full by a delegated reader, not by me directly.
- d3-lite's grounding ability rests on two Ariadne datapoints whose exact definition (mean probability vs accuracy) should be confirmed.
- LELA's ZESHEL numbers are normalized accuracy: they assume the gold entity is among the candidates, so real end-to-end accuracy is lower.\[1\]\[15\]
- Several sources are 2026 preprints not yet peer-reviewed.
- NLI zero-shot classifiers and reward/verifier models were not researched in depth this round. No claims about their grounding accuracy should be inferred from this report.
- No evidence was found for coverage-risk curves in entity linking or KGQA. The 10/5/1% coverage estimates above are reasoned extrapolations from conformal judging studies.

## Sources

1. [LELA: an LLM-based Entity Linking Approach with Zero-Shot Domain Adaptation](https://arxiv.org/pdf/2601.05192)
2. <https://arxiv.org/html/2602.13110v2>
3. <https://arxiv.org/html/2608.17994v1>
4. [vLLM Semantic Router Releases Decision 3.0 Open-Weight Decision Models](https://ccleaks.com/news/decision-3-0-open-weights-oct-2026)
5. [vllm-sr/d3-lite · Hugging Face](https://huggingface.co/vllm-sr/d3-lite)
6. [LELA: an LLM-based Entity Linking Approachwith Zero-Shot Domain Adaptation](https://arxiv.org/html/2601.05192v1)
7. <https://arxiv.org/html/2608.27470v1>
8. [Beyond Post-Hoc Temperature Scaling: Bilevel Optimization for LLM Calibration](https://arxiv.org/html/2608.07419)
9. [Calibration of Pre-trained Transformers](https://arxiv.org/pdf/2003.07892)
10. [\[2603.00924\] Conformal Prediction for Risk-Controlled Medical Entity Extraction Across Clinical Domains](https://arxiv.org/abs/2603.00924)
11. <https://arxiv.org/pdf/2506.20178>
12. [Judge, Retrieve, or Abstain: Uncertainty-Guarded LLM Judging with Provable Risk Guarantees](https://www.alphaxiv.org/abs/2608.17994)
13. [SCOPE: Selective Conformal Optimized Pairwise LLM Judging](https://arxiv.org/html/2602.13110v3)
14. [AttnLink: Turning Attention into Schema Links for Text-to-SQL](https://arxiv.org/html/2608.00693)
15. [Understanding Hard Negatives in Noise Contrastive Estimation](https://arxiv.org/pdf/2104.06245)
16. [GitHub - DeepGraphLearning/ULTRA: A foundation model for knowledge graph reasoning · GitHub](https://github.com/DeepGraphLearning/ULTRA)
17. [Paper page - Towards Foundation Models for Knowledge Graph Reasoning](https://huggingface.co/papers/2310.04562)
18. [Illusions of Relevance: Arbitrary Content Injection Attacks Deceive Retrievers, Rerankers, and LLM Judges](https://arxiv.org/html/2501.18536)
19. [The Vulnerability of LLM Rankers to Prompt Injection Attacks](https://arxiv.org/html/2602.16752v1)
20. [BAAI/bge-reranker-v2-m3 · Superlinked](https://superlinked.com/models/baai-bge-reranker-v2-m3)
21. [Scalable Zero-shot Entity Linking with Dense Entity Retrieval](https://www.alphaxiv.org/abs/1911.03814)
22. [ReFinED: An Efficient Zero-shot-capable Approach to End-to-End Entity Linking](https://arxiv.org/pdf/2207.04108)
23. [RESDSQL: Decoupling Schema Linking and Skeleton Parsing for Text-to-SQL](https://ojs.aaai.org/index.php/AAAI/article/view/26535/26307)
24. [The Embedder's Dilemma: LLMs Are Better, but at What Cost?](https://arxiv.org/pdf/2608.12875)
25. [\[2309.03882\] Large Language Models Are Not Robust Multiple Choice Selectors](https://arxiv.org/abs/2309.03882)
26. [Large Language Models Are Not Robust Multiple Choice Selectors](https://mlanthology.org/iclr/2024/zheng2024iclr-large/)
27. [GitHub - facebookresearch/BLINK: Entity Linker solution · GitHub](https://github.com/facebookresearch/BLINK)
28. [GitHub - amazon-science/ReFinED: ReFinED is an efficient and accurate entity linking (EL) system. · GitHub](https://github.com/amazon-science/ReFinED)
29. [␣ ␣ In-depth Analysis of LLM-based Schema Linking](https://openproceedings.org/2026/conf/edbt/paper-24.pdf)
30. [Proxy-based Zero-Shot Entity Linking by Effective Candidate Retrieval](https://arxiv.org/pdf/2301.13318)
31. [Reveal the Unknown: Out-of-Knowledge-Base Mention Discovery with Entity Linking](https://arxiv.org/pdf/2302.07189)
32. [SupportCal: Label-Free Calibration of Post-Trained LLMs via Reference Support and Corroboration](https://arxiv.org/pdf/2609.24303)
33. [Thermometer: Towards Universal Calibration for Large Language Models](https://arxiv.org/pdf/2403.08819)
34. [Meet, Compare, or Abstain: LatWeave for Deterministic Multi-Hop Question Answering on Knowledge Lattices](https://arxiv.org/pdf/2609.27225)
35. <https://arxiv.org/pdf/2505.13432>
36. [Ground-Truth Subgraphs for Better Training and Evaluation of Knowledge Graph Augmented LLMs](https://arxiv.org/html/2511.04473v3)
37. [Knowledge Graph Simple Question Answering for Unseen Domains](https://arxiv.org/pdf/2005.12040)
38. [Coverage Guarantees for Pseudo-Calibrated Conformal Prediction under Distribution Shift](https://arxiv.org/html/2602.14913v3)
39. [Continual Calibration: Coverage Can Collapse Before Accuracy in Lifelong LLM Fine-Tuning](https://arxiv.org/html/2604.23987v1)
40. [\[2505.13432\] Synthetic-Powered Predictive Inference - ar5iv - arXiv](https://ar5iv.labs.arxiv.org/html/2505.13432)
41. [Conformalized Large Language Models under Configuration Shift](https://arxiv.org/html/2608.01460v1)
42. [Conformity Breaks Conformal Prediction](https://arxiv.org/pdf/2609.04445)
43. [Online Conformal Abstention for Factuality Control Under Adversarial Bandit Feedback](https://arxiv.org/pdf/2506.14067)
44. [Selective "Selective Prediction": Reducing Unnecessary Abstention in Vision-Language Reasoning](https://arxiv.org/pdf/2402.15610)
45. [What Is Abstention](https://arize.com/glossary/abstention/)
46. [GitHub - nju-websoft/KG-ICL: A Knowledge Graph Foundation Model for Universal In-Context Reasoning, NeurIPS 2024 · GitHub](https://github.com/nju-websoft/KG-ICL)
47. [SEMMA: A Semantic Aware Knowledge Graph Foundation Model](https://arxiv.org/pdf/2505.20422)
48. [On Large Language Models’ Selection Bias in Multi-Choice Questions](https://arxiv.org/html/2309.03882v2)
49. [\[2506.20178\] COIN: Uncertainty-Guarding Selective Question Answering for Foundation Models with Provable Risk Guarantees](https://arxiv.org/abs/2506.20178)
50. [SCOPE: Selective Conformal Optimized Pairwise LLM Judging](https://arxiv.org/abs/2602.13110)
51. [Judge, Retrieve, or Abstain: Uncertainty-Guarded LLM Judging with Provable Risk Guarantees](https://arxiv.org/abs/2608.17994)
52. [\[2505.13432\] Synthetic-Powered Predictive Inference](https://arxiv.org/abs/2505.13432)
53. [MSc-SQL: Multi-Sample Critiquing Small Language Models For Text-To-SQL Translation](https://arxiv.org/pdf/2410.12916)
