import { buildLaneTask, buildRun, buildTraceEntries } from "./adapt";
import type {
  EvidenceRecord,
  FederatedEvidence,
  Limits,
  Plan,
  ProbeSource,
  Provenance,
  ServerAnswer,
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
    related: [
      { id: "M1038", name: "Execution Prevention" },
      { id: "M1026", name: "Privileged Account Management" },
    ],
    join_values: ["T1047"],
    provenance: attackProv("technique--01", NEO4J_QUERY),
  },
  {
    primary_id: "T1546.003",
    id_scheme: "attack-id",
    label: "Technique",
    name: "WMI Event Subscription",
    properties: { tactic: "persistence", platform: "Windows" },
    related: [{ id: "M1038", name: "Execution Prevention" }],
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
    { key: "classify", label: "Intent", status: "pass", target: "stage-draft" },
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
          json: `{ "label":"Technique", "join_values":["T1047"],\n  "provenance":"ATT&CK v19.0 / neo4j" }`,
          fullJson: JSON.stringify(ATTACK_RECORDS[0], null, 2),
          query: NEO4J_QUERY,
          provenanceMeta: "attack/neo4j · technique--01 · 2026-06-29 19:00:00Z",
        },
        {
          id: "T1546.003",
          accent: "teal",
          name: "WMI Event Subscription",
          json: `{ "label":"Technique", "join_values":["T1546.003"],\n  "provenance":"ATT&CK v19.0 / neo4j" }`,
          fullJson: JSON.stringify(ATTACK_RECORDS[1], null, 2),
          query: NEO4J_QUERY,
          provenanceMeta: "attack/neo4j · technique--02 · 2026-06-29 19:00:00Z",
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
          json: `{ "label":"AttackPattern", "join_values":["T1047"],\n  "provenance":"CAPEC v3.9 / gremlin" }`,
          fullJson: JSON.stringify(CAPEC_RECORDS[0], null, 2),
          query: GREMLIN_QUERY,
          provenanceMeta: "capec/gremlin · capec--549 · 2026-06-29 19:00:00Z",
        },
        {
          id: "CAPEC-563",
          accent: "amber",
          name: "Add Malicious File to Shared Webroot",
          json: `{ "label":"AttackPattern", "join_values":["T1546.003"],\n  "provenance":"CAPEC v3.9 / gremlin" }`,
          fullJson: JSON.stringify(CAPEC_RECORDS[1], null, 2),
          query: GREMLIN_QUERY,
          provenanceMeta: "capec/gremlin · capec--563 · 2026-06-29 19:00:00Z",
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
    // The verified-synthesis view (Step 6/7): every claim cited, 3/3 supported.
    synthesis: {
      headline: "Grounded answer from 2 source(s); 1 cross-source correlation.",
      narrative:
        "ATT&CK technique T1047 (Windows Management Instrumentation) is present, and " +
        "two CAPEC attack patterns (CAPEC-549, CAPEC-563) relate to it. T1047 is " +
        "corroborated across both the ATT&CK and CAPEC sources.",
      claims: [
        {
          text: "Found ATT&CK record T1047: Windows Management Instrumentation.",
          kind: "fact",
          chips: [
            { id: "T1047", source: "attack/neo4j", accent: "teal", target: "lane-neo4j" },
          ],
          entityIds: ["T1047"],
          contested: [],
        },
        {
          text: "Found 2 CAPEC record(s) including CAPEC-549, CAPEC-563.",
          kind: "fact",
          chips: [
            { id: "CAPEC-549", source: "capec/gremlin", accent: "amber", target: "lane-gremlin" },
            { id: "CAPEC-563", source: "capec/gremlin", accent: "amber", target: "lane-gremlin" },
          ],
          entityIds: ["CAPEC-549", "CAPEC-563"],
          contested: [],
        },
        {
          text: "The identifier T1047 is corroborated across attack and capec (2 record(s) share it).",
          kind: "correlation",
          chips: [
            { id: "T1047", source: "attack/neo4j", accent: "teal", target: "lane-neo4j" },
            { id: "CAPEC-549", source: "capec/gremlin", accent: "amber", target: "lane-gremlin" },
          ],
          entityIds: ["T1047", "CAPEC-549"],
          contested: [],
        },
      ],
      abstentions: [],
      flagged: [],
      conflicts: [],
      notes: [],
      composer: "deterministic",
      fallbackReason: null,
      verification: {
        supported: 3,
        total: 3,
        unsupportedRate: 0,
        repairedAbstentions: 0,
        ok: true,
        conflictCount: 0,
      },
      // Provenance-exact edges (Option B): the verifier's CAPEC→ATT&CK
      // mappings plus the technique records' MITIGATES relationships.
      edges: [
        { source: "CAPEC-549", target: "T1047", rel: "mapsTo" },
        { source: "CAPEC-563", target: "T1546.003", rel: "mapsTo" },
        { source: "T1047", target: "M1038", rel: "mitigatedBy" },
        { source: "T1047", target: "M1026", rel: "mitigatedBy" },
        { source: "T1546.003", target: "M1038", rel: "mitigatedBy" },
      ],
    },
    timings: [
      { label: "plan", ms: 4 },
      { label: "attack", ms: 38 },
      { label: "capec", ms: 51 },
      { label: "synthesis", ms: 2 },
      { label: "total", ms: 128 },
    ],
    sequencingNotes: [],
  },
  evidence: [
    {
      id: "T1047",
      accent: "teal",
      label: "Technique",
      name: "Windows Management Instrumentation",
      meta: 'join_values: ["T1047"] · ATT&CK v19.0 / neo4j',
      idScheme: "attack-id",
      backend: "neo4j",
      joinValues: ["T1047"],
      provenanceQuery: NEO4J_QUERY,
      provenanceMeta: "attack/neo4j · technique--01 · 2026-06-29 19:00:00Z",
      fullJson: JSON.stringify(ATTACK_RECORDS[0], null, 2),
    },
    {
      id: "T1546.003",
      accent: "teal",
      label: "Technique",
      name: "WMI Event Subscription",
      meta: 'join_values: ["T1546.003"] · ATT&CK v19.0 / neo4j',
      idScheme: "attack-id",
      backend: "neo4j",
      joinValues: ["T1546.003"],
      provenanceQuery: NEO4J_QUERY,
      provenanceMeta: "attack/neo4j · technique--02 · 2026-06-29 19:00:00Z",
      fullJson: JSON.stringify(ATTACK_RECORDS[1], null, 2),
    },
    {
      id: "CAPEC-549",
      accent: "amber",
      label: "AttackPattern",
      name: "Local Execution of Code",
      meta: 'join_values: ["T1047"] · CAPEC v3.9 / gremlin',
      idScheme: "capec-id",
      backend: "gremlin",
      joinValues: ["T1047"],
      provenanceQuery: GREMLIN_QUERY,
      provenanceMeta: "capec/gremlin · capec--549 · 2026-06-29 19:00:00Z",
      fullJson: JSON.stringify(CAPEC_RECORDS[0], null, 2),
    },
    {
      id: "CAPEC-563",
      accent: "amber",
      label: "AttackPattern",
      name: "Add Malicious File to Shared Webroot",
      meta: 'join_values: ["T1546.003"] · CAPEC v3.9 / gremlin',
      idScheme: "capec-id",
      backend: "gremlin",
      joinValues: ["T1546.003"],
      provenanceQuery: GREMLIN_QUERY,
      provenanceMeta: "capec/gremlin · capec--563 · 2026-06-29 19:00:00Z",
      fullJson: JSON.stringify(CAPEC_RECORDS[1], null, 2),
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

/* ---------------------------------------------------------------------------
 * Second seeded turn: a deprecated-CAPEC lookup that honestly returns empty.
 *
 * CAPEC-557 ("DEPRECATED: Schedule Software To Run") is a retired pattern. Since
 * the build now EXCLUDES Deprecated/Obsolete CAPEC entries at load
 * (exclude-at-load, mirroring ATT&CK), the pattern is absent from the loaded
 * graph — so the Gremlin lookup runs cleanly and returns zero records, and the
 * answer is an honest, grounded abstention rather than an invented result.
 * This turn demonstrates that behavior end to end (green pipeline, 0 records).
 * ------------------------------------------------------------------------- */

const DEPRECATED_GREMLIN_QUERY = `g.V().hasLabel('AttackPattern').has('capec_id','557')
 .elementMap()
 .limit(1000)`;

const DEPRECATED_PROBE: ProbeSource[] = [
  {
    dataset: "attack",
    backend: "neo4j",
    endpoint: "bolt://localhost:5456",
    live: true,
    node_count: 4369,
    observed_labels: ["Technique", "Mitigation", "Group", "Tactic"],
    reason: "",
  },
  {
    dataset: "capec",
    backend: "gremlin",
    endpoint: "ws://localhost:6455/gremlin",
    live: true,
    node_count: 4769,
    observed_labels: ["AttackPattern", "Category", "View", "Weakness"],
    reason: "",
  },
];

const DEPRECATED_PLAN: Plan = {
  request: "Does the deprecated pattern CAPEC-557 map to any ATT&CK techniques?",
  sub_questions: [
    {
      id: "sq-1",
      source: "capec",
      text: "Look up CAPEC-557 and its ATT&CK taxonomy mappings",
      entities: ["CAPEC-557"],
      limits: LIMITS,
      join_key: "attack-technique-id",
      rationale: "A single CAPEC lookup answers whether the pattern exists and what it maps to.",
    },
  ],
  joins: [],
  unsupported: [],
  assumptions: [],
  rationale: "Only CAPEC is queried; nothing to correlate until a pattern is found.",
  partial: false,
  trace: [
    {
      iteration: 1,
      drafter: "deterministic",
      gate_ok: true,
      reasons: [],
      sub_questions: 1,
      unsupported: 0,
    },
  ],
};

const DEPRECATED_RESULT: SpecialistResult = {
  task: {
    sub_question_id: "sq-1",
    source: "capec",
    text: "Look up CAPEC-557 and its ATT&CK taxonomy mappings",
    entities: ["CAPEC-557"],
    limits: LIMITS,
    join_key: "attack-technique-id",
    seed_ids: ["CAPEC-557"],
    rationale: "Resolve the pattern before attempting any cross-source join.",
  },
  query: DEPRECATED_GREMLIN_QUERY,
  records: [],
  record_count: 0,
  summary:
    "No node matches CAPEC-557 — it is Deprecated and excluded from the loaded catalog at build (exclude-at-load).",
  traces: [
    { step: "intake", ok: true, reasons: [], detail: { source: "capec", card: "capec" } },
    {
      step: "resolve",
      ok: true,
      reasons: [],
      detail: {
        labels: ["AttackPattern"],
        relationships: [],
        seed_ids: ["CAPEC-557"],
        join_key: "attack-technique-id",
      },
    },
    {
      step: "gate",
      ok: true,
      reasons: [],
      detail: {
        attempt: 1,
        template: "capec_lookup",
        query: DEPRECATED_GREMLIN_QUERY,
        injected: ["limit(1000)"],
      },
    },
    { step: "execute", ok: true, reasons: [], detail: { row_count: 0, timing_ms: 23 } },
    { step: "assess", ok: true, reasons: ["empty result set — ran cleanly"], detail: { row_count: 0 } },
    { step: "normalize", ok: true, reasons: [], detail: { record_count: 0 } },
  ],
  ok: true,
  partial: false,
  error: null,
  join_values: [],
};

const DEPRECATED_FEDERATED: FederatedEvidence = {
  request: "Does the deprecated pattern CAPEC-557 map to any ATT&CK techniques?",
  results: [DEPRECATED_RESULT],
  unsupported: [
    {
      description: "CAPEC-557 → ATT&CK mapping",
      reason:
        "CAPEC-557 is Deprecated; retired CAPEC entries are excluded at load, so no such node exists in the graph.",
    },
  ],
  skipped: [],
  partial: false,
  join_index: {},
  cross_source_join_values: [],
};

const DEPRECATED_ANSWER: ServerAnswer = {
  headline:
    "The loaded CAPEC graph doesn't establish this: CAPEC-557 (“DEPRECATED: Schedule Software To Run”) is a retired pattern, excluded at load, so the lookup returns no records.",
  sections: [
    {
      source: "capec",
      backend: "gremlin",
      ok: true,
      partial: false,
      summary:
        "CAPEC-557 returned 0 records — the pattern is Deprecated and is excluded from the loaded catalog (exclude-at-load, mirroring ATT&CK).",
      record_ids: [],
      record_count: 0,
    },
  ],
  cross_source: [],
  unsupported: [
    {
      description: "CAPEC-557 → ATT&CK mapping",
      reason:
        "CAPEC-557 is Deprecated; retired CAPEC entries are excluded at load, so no such node exists in the graph.",
    },
  ],
  // The verified synthesis (Step 6): zero claims, one honest abstention whose
  // proof is the exact executed Gremlin query — the shape SynthesizedAnswer
  // .to_dict() emits on the live `answer` event.
  synthesis: {
    request: "Does the deprecated pattern CAPEC-557 map to any ATT&CK techniques?",
    headline:
      "No records were returned by the routed specialists; 1 question(s) the sources don't establish.",
    narrative:
      "The CAPEC source doesn't establish this — the executed query ran cleanly and returned no matching records for CAPEC-557's ATT&CK mappings.",
    claims: [],
    rendered_claims: [],
    abstentions: [
      {
        sub_question_id: "sq-1",
        source: "capec",
        statement:
          "The capec source doesn't establish this — the executed query ran cleanly and returned no matching records for: Look up CAPEC-557 and its ATT&CK taxonomy mappings",
        query: DEPRECATED_GREMLIN_QUERY,
      },
    ],
    notes: [
      "The planner marked 1 part unsupported: CAPEC-557 → ATT&CK mapping.",
    ],
    composer: "deterministic",
    fallback_reason: null,
    verification: {
      verdicts: [],
      claim_count: 0,
      supported_count: 0,
      unsupported_count: 0,
      unsupported_claim_rate: 0,
      repaired_abstentions: 0,
      ok: true,
    },
  },
  status: "answered",
  exit_code: 0,
};

/**
 * The abstention turn, assembled the same way the live stream builds a turn:
 * pure {@link buildRun} over probe + plan + evidence + answer payloads.
 */
export const deprecatedCapecRun: WorkbenchRun = buildRun({
  id: "turn-2",
  question: "Does the deprecated pattern CAPEC-557 map to any ATT&CK techniques?",
  mode: "query",
  drafter: "deterministic",
  liveSources: DEPRECATED_PROBE,
  plan: DEPRECATED_PLAN,
  evidence: DEPRECATED_FEDERATED,
  answer: DEPRECATED_ANSWER,
  status: "answered",
  exitCode: 0,
  elapsedMs: 176,
  createdAt: 0,
});

export const initialRun = wmiCapecRun;

/** Both seeded turns of the opening conversation, oldest first. */
export const seededRuns: WorkbenchRun[] = [wmiCapecRun, deprecatedCapecRun];
