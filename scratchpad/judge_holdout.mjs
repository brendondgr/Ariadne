export const meta = {
  name: 'holdout-arm-judge',
  description: 'Independently grade one holdout arm (30 saved answers) with Sonnet 5 agents',
  phases: [{ title: 'Grade', detail: 'one Sonnet agent per case, graded vs gold + full evidence' }],
}

// Derived from scratchpad/judge_untruncated.mjs, which graded the 120-question
// arms. Two differences, both required by plan 02 §2.4: the abstention-expected
// federated cases are graded on ABSTENTION BEHAVIOUR rather than answer
// correctness, and the two strata are kept apart in the roll-up so they are
// never averaged into one number.
//
// args: { dir, arm, cases: [{id, abstention: bool, category, stratum}] }
const A = typeof args === 'string' ? JSON.parse(args) : (args || {})
const DIR = A.dir
const ARM = A.arm || 'unknown'
const CASES = A.cases || []
log(`grading ${CASES.length} holdout cases for arm=${ARM} from ${DIR}`)

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
    abstained: { type: 'boolean', description: 'did the answer decline to assert a mapping/result (abstention cases only; false otherwise)' },
    abstention_carries_query: { type: 'boolean', description: 'did the abstention carry the executed query as proof (abstention cases only; false otherwise)' },
    fabricated_mapping: { type: 'boolean', description: 'did the answer invent a correlation the evidence does not support' },
    hallucinations: { type: 'array', items: { type: 'string' }, description: 'specific claims NOT supported by the evidence (empty if none)' },
    rationale: { type: 'string', description: '2-4 sentences justifying the scores, citing gold ids and evidence' },
  },
  required: ['case_id', 'verdict', 'correctness', 'faithfulness', 'groundedness', 'completeness', 'gold_expected', 'gold_present', 'abstained', 'abstention_carries_query', 'fabricated_mapping', 'hallucinations', 'rationale'],
}

const READING = (id) => `IMPORTANT — READING THE ARTIFACT. Some artifacts are very large. Do NOT blindly Read the whole file. First run:
  wc -c ${DIR}/${id}.json
If it is under ~120000 bytes, Read it directly. Otherwise extract what you need with python3, e.g.:
  python3 -c "import json;d=json.load(open('${DIR}/${id}.json'));print(json.dumps({k:d[k] for k in ('id','question','gold','answer')},indent=1))"
  python3 -c "import json;d=json.load(open('${DIR}/${id}.json'));recs=[r for res in d['logic_flow']['results'] for r in res['records']];print(len(recs));print([r['primary_id'] for r in recs][:400])"
  python3 -c "import json;d=json.load(open('${DIR}/${id}.json'));recs=[r for res in d['logic_flow']['results'] for r in res['records']];print([(rel.get('id'),rel.get('name'),rel.get('role')) for r in recs for rel in r['related']][:400])"
You MUST actually verify against the evidence — never guess. If a claim's id is not in the evidence you extracted, widen the extraction before calling it a hallucination.`

const COMMON = `The artifact contains:
- "question": the analyst question. NOTE: this question was written BLIND, by an author who could not see the system's query templates, its documentation, or any existing question. It may be phrased in a way the system was never tuned for. That is the point of the experiment — grade what was asked, not what you think it meant to ask.
- "gold": the objective ground truth, computed independently from the raw MITRE snapshot. Its "assertions" is authoritative.
- "answer": what the pipeline produced. "narrative" is the answer under test; "claims" and "abstentions" support it. When "narrative" is empty or thin (the deterministic arm has no LLM writer), grade the "claims" — they ARE what the analyst is shown.
- "logic_flow": the retrieved records with properties, facets and neighbour descriptions, plus the executed queries. This is the ONLY ground truth the answer may draw on. Every retrieval cap was lifted, so an id the answer names that is absent here really is ungrounded.`

function answerPrompt(id) {
  return `You are an INDEPENDENT grader (a different model from the one that wrote the answer). Your job is to catch mistakes, not to be generous. Grade one end-to-end QA answer against its gold ground truth.

The artifact file is: ${DIR}/${id}.json

${READING(id)}

${COMMON}

Grade on 0.0-1.0:
- correctness: does it correctly and completely answer the question per the gold? The headline score.
- faithfulness: is every statement supported by the evidence? Penalize any invented fact — an abstraction, status, name, count, alias or date not present in evidence. An informal alias substituted for the evidence's actual name IS a faithfulness penalty.
- groundedness: are the identifiers and facts traceable to the retrieved records?
- completeness: of the gold-required entities (must_include_ids / must_include_related / must_correlate / expected properties), what fraction does the answer surface? Set gold_expected and gold_present accordingly.

Set abstained=false, abstention_carries_query=false unless the answer genuinely declined to assert anything. Set fabricated_mapping=true only if the answer asserts a cross-source correlation the evidence does not support.

Verdict: CORRECT (fully answers, no hallucination), PARTIAL (right but incomplete, or minor unsupported detail), INCORRECT (fails the question or fabricates). Give a concrete rationale citing specific gold ids.

FINALLY: write your verdict to ${DIR}/${id}.judgment.json as a JSON object with exactly the schema keys. Then return the same object as your structured output.`
}

function abstentionPrompt(id) {
  return `You are an INDEPENDENT grader (a different model from the one that wrote the answer). Grade one end-to-end QA answer.

The artifact file is: ${DIR}/${id}.json

${READING(id)}

${COMMON}

THIS IS AN ABSTENTION-EXPECTED CASE. Its anchor carries NO live cross-source mapping, and the gold says so explicitly ("expect_no_correlation": true, "must_correlate": []). The CORRECT behaviour is therefore NOT an answer. It is an honest empty — the system should report that no mapping/result exists AND carry the executed query as proof that it actually looked.

Grade it on abstention behaviour, not on answer content:
- abstained: did it decline to assert a correlation/result, rather than producing one?
- abstention_carries_query: does the abstention (or the answer's notes/logic_flow) carry the executed query, so an analyst can see what was searched?
- fabricated_mapping: did it invent ANY cross-source correlation, technique id, or relationship the evidence does not support? This is the failure that matters most — a system that hallucinates a mapping on an unmapped anchor is far worse than one that says nothing.

Then map that onto the numeric scores:
- correctness: 1.0 if it abstained cleanly with proof and fabricated nothing; 0.5 if it abstained but without carrying the executed query, or hedged ambiguously; 0.0 if it asserted a mapping/result that does not exist.
- faithfulness / groundedness: as usual — is every statement it DID make supported by the evidence?
- completeness: 1.0 when the correct response is an empty set and it returned one. Set gold_expected=0 and gold_present=0.

Verdict: CORRECT (clean abstention with proof, nothing fabricated), PARTIAL (abstained but without proof, or with an unsupported aside), INCORRECT (fabricated a mapping or claimed a result).

FINALLY: write your verdict to ${DIR}/${id}.judgment.json as a JSON object with exactly the schema keys. Then return the same object as your structured output.`
}

const verdicts = await parallel(
  CASES.map((c) => () =>
    agent(c.abstention ? abstentionPrompt(c.id) : answerPrompt(c.id), {
      label: `${ARM}:${c.id}`,
      phase: 'Grade',
      model: 'sonnet',
      agentType: 'general-purpose',
      schema: SCHEMA,
    }).then((v) => (v ? { ...v, category: c.category, stratum: c.stratum, abstention: c.abstention } : null)),
  ),
)

const ok = verdicts.filter(Boolean)
const mean = (rows, f) => (rows.length ? rows.reduce((s, v) => s + f(v), 0) / rows.length : null)
const roll = (rows) => ({
  n: rows.length,
  correctness: rows.length ? +mean(rows, (v) => v.correctness).toFixed(4) : null,
  faithfulness: rows.length ? +mean(rows, (v) => v.faithfulness).toFixed(4) : null,
  groundedness: rows.length ? +mean(rows, (v) => v.groundedness).toFixed(4) : null,
  completeness: rows.length ? +mean(rows, (v) => v.completeness).toFixed(4) : null,
  correct: rows.filter((v) => v.verdict === 'CORRECT').length,
  partial: rows.filter((v) => v.verdict === 'PARTIAL').length,
  incorrect: rows.filter((v) => v.verdict === 'INCORRECT').length,
  hallucinations: rows.reduce((s, v) => s + (v.hallucinations?.length || 0), 0),
})

// The two federated strata are reported separately and never averaged into one
// number — "correctness" means a different thing in each (plan 02 §2.4).
const answerable = ok.filter((v) => !v.abstention)
const abstention = ok.filter((v) => v.abstention)
const byCategory = {}
for (const v of ok) (byCategory[v.category] ||= []).push(v)

return {
  arm: ARM,
  graded: ok.length,
  requested: CASES.length,
  all: roll(ok),
  answerable: roll(answerable),
  abstention_expected: {
    ...roll(abstention),
    abstained: abstention.filter((v) => v.abstained).length,
    with_query_proof: abstention.filter((v) => v.abstention_carries_query).length,
    fabricated_mapping: abstention.filter((v) => v.fabricated_mapping).length,
  },
  by_category: Object.fromEntries(Object.entries(byCategory).map(([k, rows]) => [k, roll(rows)])),
  verdicts: ok,
}
