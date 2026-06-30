import { buildLaneTask, buildTraceEntries } from "./adapt";
import type {
  EvidenceRecord,
  FederatedEvidence,
  Limits,
  Provenance,
  SpecialistResult,
  WorkbenchRun,
} from "./types";

/**
 * The "WMI execution → CAPEC mapping" sample run from the mockup, expressed
 * as a fully-typed {@link WorkbenchRun}. Components render from this until a
 * live streaming backend replaces it.
 */

const LIMITS: Limits = {
  max_traversal_depth: 3,
  max_result_rows: 1000,
  query_timeout_ms: 5000,
};

const NEO4J_QUERY = `MATCH (t:Technique)-[:USES]->(m:Method)
WHERE m.name = 'WMI'
RETURN t.external_id, t.name
LIMIT 1000`;

const GREMLIN_QUERY = `g.V().has('capec','maps_to','T1047')
 .out('enables')
 .limit(1000)`;

function attackProv(recordId: string, query: string): Provenance {
  return {
    source: "MITRE ATT&CK Enterprise",
    dataset: "attack",
    backend: "neo4j",
    query,
    record_id: recordId,
    timestamp: "2026-06-29T19:00:00+00:00",
  };
}

function capecProv(recordId: string, query: string): Provenance {
  return {
    source: "MITRE CAPEC",
    dataset: "capec",
    backend: "gremlin",
    query,
    record_id: recordId,
    timestamp: "2026-06-29T19:00:00+00:00",
  };
}

const ATTACK_RECORDS: EvidenceRecord[] = [
  {
    primary_id: "T1047",
    id_scheme: "attack-id",
    label: "Technique",
    name: "Windows Management Instrumentation",
    properties: { tactic: "execution", platform: "Windows" },
    related: [],
    join_values: ["T1047"],
    provenance: attackProv("technique--01", NEO4J_QUERY),
  },
  {
    primary_id: "T1546.003",
    id_scheme: "attack-id",
    label: "Technique",
    name: "WMI Event Subscription",
    properties: { tactic: "persistence", platform: "Windows" },
    related: [],
    join_values: ["T1546.003"],
    provenance: attackProv("technique--02", NEO4J_QUERY),
  },
];

const CAPEC_RECORDS: EvidenceRecord[] = [
  {
    primary_id: "CAPEC-549",
    id_scheme: "capec-id",
    label: "AttackPattern",
    name: "Local Execution of Code",
    properties: { abstraction: "Standard" },
    related: [],
    join_values: ["T1047"],
    provenance: capecProv("capec--549", GREMLIN_QUERY),
  },
  {
    primary_id: "CAPEC-563",
    id_scheme: "capec-id",
    label: "AttackPattern",
    name: "Add Malicious File to Shared Webroot",
    properties: { abstraction: "Detailed" },
    related: [],
    join_values: ["T1546.003"],
    provenance: capecProv("capec--563", GREMLIN_QUERY),
  },
];

const NEO4J_RESULT: SpecialistResult = {
  task: {
    sub_question_id: "sq-1",
    source: "attack",
    text: "techniques using WMI for execution (ATT&CK)",
    entities: ["WMI", "T1047"],
    limits: LIMITS,
    join_key: "attack-technique-id",
    seed_ids: [],
    rationale: "WMI execution maps to ATT&CK technique T1047.",
  },
  query: NEO4J_QUERY,
  records: ATTACK_RECORDS,
  record_count: ATTACK_RECORDS.length,
  summary: "Two ATT&CK techniques use WMI for execution: T1047 and T1546.003.",
  traces: [
    { step: "intake", ok: true, reasons: [], detail: { source: "attack", card: "attack" } },
    {
      step: "resolve",
      ok: true,
      reasons: [],
      detail: {
        labels: ["Technique"],
        relationships: ["USES"],
        seed_ids: [],
        join_key: "attack-technique-id",
      },
    },
    {
      step: "gate",
      ok: true,
      reasons: [],
      detail: {
        attempt: 1,
        template: "match_method",
        query: NEO4J_QUERY,
        injected: ["LIMIT 1000"],
      },
    },
    { step: "execute", ok: true, reasons: [], detail: { row_count: 2, timing_ms: 42 } },
    { step: "assess", ok: true, reasons: [], detail: { row_count: 2 } },
    { step: "normalize", ok: true, reasons: [], detail: { record_count: 2 } },
  ],
  ok: true,
  partial: false,
  error: null,
  join_values: ["T1047", "T1546.003"],
};

const GREMLIN_RESULT: SpecialistResult = {
  task: {
    sub_question_id: "sq-2",
    source: "capec",
    text: "CAPEC patterns mapped to those techniques",
    entities: ["CAPEC", "T1047"],
    limits: LIMITS,
    join_key: "attack-technique-id",
    seed_ids: ["T1047"],
    rationale: "CAPEC patterns map to ATT&CK techniques via MAPS_TO.",
  },
  query: GREMLIN_QUERY,
  records: CAPEC_RECORDS,
  record_count: CAPEC_RECORDS.length,
  summary: "Two CAPEC attack patterns map to the WMI techniques: CAPEC-549 and CAPEC-563.",
  traces: [
    { step: "intake", ok: true, reasons: [], detail: { source: "capec", card: "capec" } },
    {
      step: "resolve",
      ok: true,
      reasons: [],
      detail: {
        labels: ["AttackPattern"],
        relationships: ["MAPS_TO", "enables"],
        seed_ids: ["T1047"],
        join_key: "attack-technique-id",
      },
    },
    {
      step: "gate",
      ok: true,
      reasons: [],
      detail: {
        attempt: 1,
        template: "maps_to_enables",
        query: GREMLIN_QUERY,
        injected: ["limit(1000)"],
      },
    },
    { step: "execute", ok: true, reasons: [], detail: { row_count: 2, timing_ms: 61 } },
    { step: "assess", ok: true, reasons: [], detail: { row_count: 2 } },
    { step: "normalize", ok: true, reasons: [], detail: { record_count: 2 } },
  ],
  ok: true,
  partial: false,
  error: null,
  join_values: ["T1047", "T1546.003"],
};

const FEDERATED: FederatedEvidence = {
  request:
    "Which ATT&CK techniques use WMI for execution, and what CAPEC attack patterns map to them?",
  results: [NEO4J_RESULT, GREMLIN_RESULT],
  unsupported: [],
  skipped: [],
  partial: false,
  join_index: {
    T1047: [
      { source: "attack", primary_id: "T1047", name: "Windows Management Instrumentation" },
      { source: "capec", primary_id: "CAPEC-549", name: "Local Execution of Code" },
    ],
    "T1546.003": [
      { source: "attack", primary_id: "T1546.003", name: "WMI Event Subscription" },
      { source: "capec", primary_id: "CAPEC-563", name: "Add Malicious File to Shared Webroot" },
    ],
  },
  cross_source_join_values: ["T1047", "T1546.003"],
};

const ALL_STEPS_PASS = (
  [
    ["intake", "intake"],
    ["resolve", "resolve"],
    ["gate", "pre-run gate"],
    ["execute", "execute"],
    ["assess", "assess"],
    ["normalize", "normalize"],
  ] as const
).map(([key, label]) => ({
  key,
  label,
  status: "pass" as const,
  emphasis: key === "gate" || key === "normalize",
}));

export const wmiCapecRun: WorkbenchRun = {
  id: "turn-1",
  question:
    "Which ATT&CK techniques use WMI for execution, and what CAPEC attack patterns map to them?",
  mode: "query",
  drafter: "deterministic",
  status: "answered",
  exitCode: 0,
  elapsedMs: 318,
  createdAt: 0,
  liveSources: [
    { backend: "neo4j", status: "live", nodes: 12540 },
    { backend: "gremlin", status: "live", nodes: 8210 },
  ],
  stepper: [
    { key: "probe", label: "Probe", status: "pass", target: "stage-probe" },
    { key: "plan", label: "Plan", status: "pass", target: "stage-gate" },
    { key: "specialists", label: "Specialists", status: "pass", target: "lane-neo4j" },
    { key: "evidence", label: "Evidence", status: "pass", target: "lane-gremlin" },
    { key: "answer", label: "Answer", status: "pass", target: "stage-emit" },
  ],
  plannerStages: [
    {
      id: "stage-probe",
      index: "①",
      title: "Probe live sources",
      status: "pass",
      summary: "neo4j LIVE · 12,540 · gremlin LIVE · 8,210",
      liveSources: [
        { backend: "neo4j", status: "live", nodes: 12540 },
        { backend: "gremlin", status: "live", nodes: 8210 },
      ],
      code: `# live_sources()
{
  "neo4j":   { "status": "live", "nodes": 12540 },
  "gremlin": { "status": "live", "nodes": 8210 }
}`,
      codeLang: "json",
    },
    {
      id: "stage-draft",
      index: "②",
      title: "Draft plan",
      status: "pass",
      summary: "drafter deterministic · 2 sub-questions proposed",
      code: `# proposed sub-questions
[
  "techniques using WMI for execution (ATT&CK)",
  "CAPEC patterns mapped to those techniques"
]`,
      codeLang: "json",
    },
    {
      id: "stage-gate",
      index: "③",
      title: "Plan gate",
      status: "pass",
      summary: "passed · 0 rejections",
      shield: true,
      tag: "deterministic",
      code: `# EvaluatorTrace · plan_gate
{ "verdict": "pass", "checks": [
    "sub_questions_resolvable",
    "entities_bound_to_sources",
    "join_keys_declared"
] }`,
      codeLang: "json",
      codeEmphasis: true,
    },
    {
      id: "stage-emit",
      index: "④",
      title: "Emit plan",
      status: "pass",
      summary: "entities [WMI, T1047] · join key external_id",
      code: `{
  "limit": 1000,
  "join_keys": ["external_id"],
  "unsupported": [],
  "assumptions": ["WMI == T1047 alias"]
}`,
      codeLang: "json",
    },
  ],
  lanes: [
    {
      id: "lane-neo4j",
      badge: "Cypher · neo4j",
      backend: "neo4j",
      accent: "teal",
      title: "Techniques using WMI",
      rows: 2,
      ms: 42,
      language: "cypher",
      query: NEO4J_QUERY,
      steps: ALL_STEPS_PASS,
      task: buildLaneTask(NEO4J_RESULT.task),
      traceEntries: buildTraceEntries(NEO4J_RESULT),
      error: null,
      records: [
        {
          id: "T1047",
          accent: "teal",
          name: "Windows Management Instrumentation",
          json: `{ "label":"Technique", "join_values":["T1047"],
  "provenance":"ATT&CK v19.0 / neo4j" }`,
        },
        {
          id: "T1546.003",
          accent: "teal",
          name: "WMI Event Subscription",
          json: `{ "label":"Technique", "join_values":["T1546.003"],
  "provenance":"ATT&CK v19.0 / neo4j" }`,
        },
      ],
    },
    {
      id: "lane-gremlin",
      badge: "Gremlin · capec",
      backend: "gremlin",
      accent: "amber",
      title: "Mapped CAPEC patterns",
      rows: 2,
      ms: 61,
      language: "gremlin",
      query: GREMLIN_QUERY,
      steps: ALL_STEPS_PASS,
      task: buildLaneTask(GREMLIN_RESULT.task),
      traceEntries: buildTraceEntries(GREMLIN_RESULT),
      error: null,
      records: [
        {
          id: "CAPEC-549",
          accent: "amber",
          name: "Local Execution of Code",
          json: `{ "label":"AttackPattern", "join_values":["T1047"],
  "provenance":"CAPEC v3.9 / gremlin" }`,
        },
        {
          id: "CAPEC-563",
          accent: "amber",
          name: "Add Malicious File to Shared Webroot",
          json: `{ "label":"AttackPattern", "join_values":["T1546.003"],
  "provenance":"CAPEC v3.9 / gremlin" }`,
        },
      ],
    },
  ],
  answer: {
    paragraphs: [
      {
        segments: [
          {
            kind: "text",
            text:
              "Two ATT&CK techniques in the loaded corpus use Windows Management Instrumentation for execution. The primary technique is ",
          },
          { kind: "chip", ref: { id: "T1047", source: "ATT&CK/neo4j", accent: "teal", target: "lane-neo4j" } },
          { kind: "text", text: ", with " },
          {
            kind: "chip",
            ref: { id: "T1546.003", source: "ATT&CK/neo4j", accent: "teal", target: "lane-neo4j" },
          },
          { kind: "text", text: " covering WMI event-subscription persistence." },
        ],
      },
      {
        segments: [
          {
            kind: "text",
            text:
              "These map to two CAPEC attack patterns that describe the adversary technique abstractly: ",
          },
          {
            kind: "chip",
            ref: { id: "CAPEC-549", source: "CAPEC/gremlin", accent: "amber", target: "lane-gremlin" },
          },
          { kind: "text", text: " (Local Execution of Code) and " },
          {
            kind: "chip",
            ref: { id: "CAPEC-563", source: "CAPEC/gremlin", accent: "amber", target: "lane-gremlin" },
          },
          { kind: "text", text: ". The join was established on the shared " },
          { kind: "mono", text: "external_id" },
          { kind: "text", text: " reference key." },
        ],
      },
      {
        segments: [
          {
            kind: "text",
            text:
              "All four records are read-only graph reads, depth ≤ 3, returned under the injected 1000-row limit. No source was unavailable; the answer is fully grounded.",
          },
        ],
      },
    ],
    joinPairs: [
      { left: "CAPEC-549", leftAccent: "amber", right: "T1047", rightAccent: "teal" },
      { left: "CAPEC-563", leftAccent: "amber", right: "T1546.003", rightAccent: "teal" },
    ],
  },
  evidence: [
    {
      id: "T1047",
      accent: "teal",
      label: "Technique",
      name: "Windows Management Instrumentation",
      meta: 'join_values: ["T1047"] · ATT&CK v19.0 / neo4j',
    },
    {
      id: "T1546.003",
      accent: "teal",
      label: "Technique",
      name: "WMI Event Subscription",
      meta: 'join_values: ["T1546.003"] · ATT&CK v19.0 / neo4j',
    },
    {
      id: "CAPEC-549",
      accent: "amber",
      label: "AttackPattern",
      name: "Local Execution of Code",
      meta: 'join_values: ["T1047"] · CAPEC v3.9 / gremlin',
    },
    {
      id: "CAPEC-563",
      accent: "amber",
      label: "AttackPattern",
      name: "Add Malicious File to Shared Webroot",
      meta: 'join_values: ["T1546.003"] · CAPEC v3.9 / gremlin',
    },
  ],
  joinIndex: [
    {
      left: "CAPEC-549",
      leftAccent: "amber",
      right: "T1047",
      rightAccent: "teal",
      matchedOn: "external_id",
      confidence: "high",
    },
    {
      left: "CAPEC-563",
      leftAccent: "amber",
      right: "T1546.003",
      rightAccent: "teal",
      matchedOn: "external_id",
      confidence: "medium",
    },
  ],
  joinKey: "external_id",
  federated: FEDERATED,
  // The seeded demo has no captured probe/plan/answer payloads or event log;
  // real streamed turns populate these for the Raw JSON tab.
  rawProbe: [],
  rawPlan: null,
  rawAnswer: null,
  events: [],
};

export const initialRun = wmiCapecRun;
