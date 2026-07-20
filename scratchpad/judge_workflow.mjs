export const meta = {
  name: 'independent-e2e-judge',
  description: 'Independently grade 120 saved e2e answers with Sonnet 5 agents against gold',
  phases: [{ title: 'Grade', detail: 'one Sonnet agent per case, scored vs gold' }],
}

// args: { dir: "docs/evaluation/answers", ids: ["C-EXE-01", ...] }
const A = typeof args === 'string' ? JSON.parse(args) : (args || {})
const DIR = A.dir || 'docs/evaluation/answers'
const IDS = A.ids || []
log(`grading ${IDS.length} cases from ${DIR}`)

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    case_id: { type: 'string' },
    verdict: { type: 'string', enum: ['CORRECT', 'PARTIAL', 'INCORRECT'] },
    correctness: { type: 'number', minimum: 0, maximum: 1 },
    faithfulness: { type: 'number', minimum: 0, maximum: 1 },
    groundedness: { type: 'number', minimum: 0, maximum: 1 },
    completeness: { type: 'number', minimum: 0, maximum: 1 },
    gold_expected: { type: 'integer', description: 'count of required gold ids/entities for this case' },
    gold_present: { type: 'integer', description: 'how many of those the answer actually surfaces' },
    hallucinations: { type: 'array', items: { type: 'string' }, description: 'specific claims NOT supported by the evidence (empty if none)' },
    rationale: { type: 'string', description: '2-4 sentences justifying the scores, citing gold ids and evidence' },
  },
  required: ['case_id', 'verdict', 'correctness', 'faithfulness', 'groundedness', 'completeness', 'gold_expected', 'gold_present', 'hallucinations', 'rationale'],
}

function prompt(id) {
  return `You are an INDEPENDENT grader (a different model from the one that wrote the answer). Your job is to catch mistakes, not to be generous. Grade one end-to-end QA answer against its gold ground truth.

Read the artifact file: ${DIR}/${id}.json

The artifact contains:
- "question": the analyst question.
- "gold": the objective ground truth. Its "assertions" is authoritative:
    - must_include_ids / must_include_related: entity ids the answer MUST surface (steps, techniques, mitigations, CWEs, etc.).
    - must_correlate: (federated) the cross-source join ids (ATT&CK T-numbers) the answer MUST state.
    - expect_names / expect_properties: expected attribute VALUES (e.g. abstraction level, status).
    - For NEGATIVE cases (id contains NEG, or gold expects nothing/min_records 0): the CORRECT answer abstains or reports no match — surfacing fabricated data is INCORRECT.
- "answer": what the pipeline produced — "narrative" (prose shown to the analyst) is the answer under test; "claims" and "abstentions" support it.
- "logic_flow" and "evidence": the retrieved records WITH related-neighbour descriptions (the real substance) and the executed queries/traces. This is the ONLY ground truth the answer may draw on.

Grade the "narrative" (using claims/abstentions as support) on 0.0-1.0:
- correctness: does it correctly and completely answer the question per the gold? This is the headline score.
- faithfulness: is every statement supported by the evidence? Penalize any invented fact (e.g. an abstraction/status/name/date not present in evidence).
- groundedness: are the identifiers and facts traceable to the retrieved records?
- completeness: of the gold-required entities (must_include_related / must_correlate / expected properties), what fraction does the answer actually surface? Set gold_expected = how many the gold requires, gold_present = how many the answer states.

List every hallucination (claim not backed by the evidence) explicitly. Pick verdict: CORRECT (fully answers, no hallucination), PARTIAL (right but incomplete, or minor unsupported detail), INCORRECT (fails the question or fabricates). Give a concrete rationale citing specific gold ids and what the answer did or didn't say. Be strict and objective — the point of this pass is to distrust the earlier same-model self-judgment.`
}

const verdicts = await parallel(
  IDS.map((id) => () =>
    agent(prompt(id), {
      label: `grade:${id}`,
      phase: 'Grade',
      model: 'sonnet',
      agentType: 'general-purpose',
      schema: SCHEMA,
    }),
  ),
)

const ok = verdicts.filter(Boolean)
const mean = (f) => (ok.length ? ok.reduce((s, v) => s + f(v), 0) / ok.length : 0)
const dist = {}
for (const v of ok) dist[v.verdict] = (dist[v.verdict] || 0) + 1

return {
  graded: ok.length,
  requested: IDS.length,
  means: {
    correctness: +mean((v) => v.correctness).toFixed(4),
    faithfulness: +mean((v) => v.faithfulness).toFixed(4),
    groundedness: +mean((v) => v.groundedness).toFixed(4),
    completeness: +mean((v) => v.completeness).toFixed(4),
  },
  verdict_distribution: dist,
  verdicts: ok,
}
