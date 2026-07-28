export const meta = {
  name: 'untruncated-arm-judge',
  description: 'Independently grade one experiment arm (120 saved answers) with Sonnet 5 agents',
  phases: [{ title: 'Grade', detail: 'one Sonnet agent per case, graded vs gold + full evidence' }],
}

// args: { dir: "docs/evaluation/experiments/untruncated/deterministic/answers", arm: "deterministic", ids: [...] }
const A = typeof args === 'string' ? JSON.parse(args) : (args || {})
const DIR = A.dir
const ARM = A.arm || 'unknown'
const IDS = A.ids || []
log(`grading ${IDS.length} cases for arm=${ARM} from ${DIR}`)

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

The artifact file is: ${DIR}/${id}.json

IMPORTANT — READING THE ARTIFACT. Some artifacts are very large (up to ~1 MB of retrieved evidence). Do NOT blindly Read the whole file. First run:
  wc -c ${DIR}/${id}.json
If it is under ~120000 bytes, Read it directly. Otherwise extract what you need with python3, e.g.:
  python3 -c "import json;d=json.load(open('${DIR}/${id}.json'));print(json.dumps({k:d[k] for k in ('id','question','gold','answer')},indent=1))"
and then query the evidence for exactly the ids/facts you need to verify, e.g.:
  python3 -c "import json;d=json.load(open('${DIR}/${id}.json'));recs=[r for res in d['logic_flow']['results'] for r in res['records']];print(len(recs));print([r['primary_id'] for r in recs][:400])"
  python3 -c "import json;d=json.load(open('${DIR}/${id}.json'));recs=[r for res in d['logic_flow']['results'] for r in res['records']];print([ (rel.get('id'),rel.get('name'),rel.get('role')) for r in recs for rel in r['related']][:400])"
You MUST actually verify against the evidence — never guess. If a claim's id is not in the evidence you extracted, widen the extraction before calling it a hallucination.

The artifact contains:
- "question": the analyst question.
- "gold": the objective ground truth. Its "assertions" is authoritative:
    - must_include_ids / must_include_related: entity ids the answer MUST surface (steps, techniques, mitigations, CWEs, etc.).
    - must_correlate: (federated) the cross-source join ids (ATT&CK T-numbers) the answer MUST state.
    - expect_names / expect_properties: expected attribute VALUES (e.g. abstraction level, status).
    - For NEGATIVE cases (id contains NEG, or gold expects nothing/min_records 0): the CORRECT answer abstains or reports no match — surfacing fabricated data is INCORRECT.
- "answer": what the pipeline produced — "narrative" (prose shown to the analyst) is the answer under test; "claims" and "abstentions" support it. NOTE: in this experiment some answers have no LLM narrative (the deterministic arm); when "narrative" is empty or thin, grade the "claims" as the answer, since the claims ARE what the analyst is shown.
- "logic_flow": the retrieved records WITH their properties, facets (adjacency counts) and related-neighbour descriptions — the real substance — plus the executed queries/traces. This is the ONLY ground truth the answer may draw on. This run deliberately lifted every retrieval cap, so the evidence is the FULL neighbourhood: an id the answer names that is absent here really is ungrounded.

Grade the answer (narrative, or the claims when there is no narrative) on 0.0-1.0:
- correctness: does it correctly and completely answer the question per the gold? This is the headline score.
- faithfulness: is every statement supported by the evidence? Penalize any invented fact (e.g. an abstraction/status/name/count/alias/date not present in evidence). An informal alias substituted for the evidence's actual name IS a faithfulness penalty.
- groundedness: are the identifiers and facts traceable to the retrieved records?
- completeness: of the gold-required entities (must_include_ids / must_include_related / must_correlate / expected properties), what fraction does the answer actually surface? Set gold_expected = how many the gold requires, gold_present = how many the answer states.

List every hallucination (any claim, count, alias, or entity not present in the evidence) explicitly as a short string. Pick verdict: CORRECT (fully answers, no hallucination), PARTIAL (right but incomplete, or minor unsupported detail), INCORRECT (fails the question or fabricates). Give a concrete rationale citing specific gold ids and what the answer did or didn't say. Be strict and objective — the point of this pass is to distrust the pipeline's own self-judgment.

FINALLY: write your verdict to ${DIR}/${id}.judgment.json as a JSON object with exactly these keys: case_id, verdict, correctness, faithfulness, groundedness, completeness, gold_expected, gold_present, hallucinations, rationale. Then return the same object as your structured output.`
}

const verdicts = await parallel(
  IDS.map((id) => () =>
    agent(prompt(id), {
      label: `${ARM}:${id}`,
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
  arm: ARM,
  graded: ok.length,
  requested: IDS.length,
  means: {
    correctness: +mean((v) => v.correctness).toFixed(4),
    faithfulness: +mean((v) => v.faithfulness).toFixed(4),
    groundedness: +mean((v) => v.groundedness).toFixed(4),
    completeness: +mean((v) => v.completeness).toFixed(4),
  },
  verdict_distribution: dist,
  total_hallucinations: ok.reduce((s, v) => s + (v.hallucinations?.length || 0), 0),
  verdicts: ok,
}
