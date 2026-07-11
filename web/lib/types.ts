/**
 * TypeScript mirrors of the Ariadne backend trace objects plus the
 * view-model types the workbench renders.
 *
 * The backend section mirrors the Python dataclasses' `to_dict()` shapes in
 * `utils/planner/schema.py` and `utils/specialists/contracts.py` /
 * `federation.py`. Keeping the names aligned means a future streaming API can
 * replace the fixtures with zero component changes — the UI is a pure
 * function of these objects.
 */

/* ============================================================
 * Backend-mirroring types (planner + specialists)
 * ============================================================ */

export interface Limits {
  max_traversal_depth: number;
  max_result_rows: number;
  query_timeout_ms: number;
}

export interface SubQuestion {
  id: string;
  source: string;
  text: string;
  entities: string[];
  limits: Limits;
  join_key: string | null;
  rationale: string;
}

export interface JoinDeclaration {
  key: string;
  sources: string[];
  on: string;
}

export interface UnsupportedPart {
  description: string;
  reason: string;
}

/** One iteration record from `Plan.trace`. */
export interface PlanTraceIteration {
  iteration: number;
  drafter: string;
  gate_ok: boolean;
  reasons: string[];
  sub_questions: number;
  unsupported: number;
}

export interface Plan {
  request: string;
  sub_questions: SubQuestion[];
  joins: JoinDeclaration[];
  unsupported: UnsupportedPart[];
  assumptions: string[];
  rationale: string;
  partial: boolean;
  trace: PlanTraceIteration[];
}

/** The six canonical checkpoints of the specialist loop, in order. */
export type SpecialistStep =
  | "intake"
  | "resolve"
  | "gate"
  | "execute"
  | "assess"
  | "normalize";

/** Deterministic grade emitted at a specialist checkpoint. */
export interface EvaluatorTrace {
  step: SpecialistStep;
  ok: boolean;
  reasons: string[];
  detail: Record<string, unknown>;
}

export interface Provenance {
  source: string;
  dataset: string;
  backend: string;
  query: string;
  record_id: string;
  timestamp: string;
}

export interface EvidenceRecord {
  primary_id: string;
  id_scheme: string;
  label: string;
  name: string;
  properties: Record<string, unknown>;
  related: Record<string, unknown>[];
  join_values: string[];
  provenance: Provenance | null;
}

export interface SpecialistTask {
  sub_question_id: string;
  source: string;
  text: string;
  entities: string[];
  limits: Limits;
  join_key: string | null;
  seed_ids: string[];
  rationale: string;
}

export interface SpecialistResult {
  task: SpecialistTask;
  query: string;
  records: EvidenceRecord[];
  record_count: number;
  summary: string;
  traces: EvaluatorTrace[];
  ok: boolean;
  partial: boolean;
  error: string | null;
  join_values: string[];
}

/** One entry in `FederatedEvidence.join_index[joinValue]`. */
export interface JoinIndexEntry {
  source: string;
  primary_id: string;
  name: string;
}

/** One dependent-sequencing audit entry: a declared-join consumer that was
 *  seeded from (or skipped because of) its producer's harvested join values. */
export interface SequencingEntry {
  consumer: string;
  producer: string;
  seed_count: number;
  truncated: boolean;
  skipped: string | null;
}

export interface FederatedEvidence {
  request: string;
  results: SpecialistResult[];
  unsupported: UnsupportedPart[];
  skipped: Record<string, unknown>[];
  partial: boolean;
  /** Optional: absent on pre-integration payloads and older fixtures. */
  sequencing?: SequencingEntry[];
  join_index: Record<string, JoinIndexEntry[]>;
  cross_source_join_values: string[];
}

/** Per-stage wall-clock timings the pipeline records (plan → specialists →
 *  synthesis → total). Emitted on the `answer` and `done` events. */
export interface PipelineTimings {
  plan_ms?: number;
  specialists?: { sub_question: string; source: string; ms: number }[];
  synthesis_ms?: number;
  total_ms?: number;
}

/* ============================================================
 * UI / view-model types
 * ============================================================ */

/** Animation-relevant status for any pipeline node. Drives Motion variants. */
export type StageStatus = "pending" | "running" | "pass" | "partial" | "fail";

/** Overall run outcome — maps to CLI exit codes 0 / 1 / 2. */
export type RunStatus = "idle" | "running" | "answered" | "partial" | "no_sources";
export type ExitCode = 0 | 1 | 2;

export type Accent = "teal" | "amber" | "sage";
export type CodeLang = "json" | "cypher" | "gremlin" | "text";

export interface LiveSource {
  backend: string;
  status: "live" | "down" | "starting";
  nodes?: number;
  reason?: string;
}

/** A segment of the inspector's top stepper / the answer card mini-stepper. */
export interface MiniStep {
  key: string;
  label: string;
  status: StageStatus;
  /** Inspector stage id this segment jumps to when clicked. */
  target?: string;
}

/** A planner-loop stage rendered in the inspector trace timeline. */
export interface PlannerStage {
  id: string;
  index: string;
  title: string;
  status: StageStatus;
  summary: string;
  liveSources?: LiveSource[];
  /** Safety checkpoint emphasis (shield + teal accent). */
  shield?: boolean;
  tag?: string;
  code: string;
  codeLang: CodeLang;
  codeEmphasis?: boolean;
}

/** A single one of the six specialist micro-steps (deduped canonical pill row). */
export interface MicroStep {
  key: SpecialistStep;
  label: string;
  status: StageStatus;
  /** The two never-cut checkpoints (pre-run gate, normalize) get emphasis. */
  emphasis?: boolean;
}

/** One evaluator trace entry surfaced in the trace tab (includes repeats for gate/execute retries). */
export interface LaneTraceEntry {
  step: SpecialistStep;
  label: string;
  status: StageStatus;
  emphasis: boolean;
  reasons: string[];
  detailJson: string;
}

/** Per-specialist task metadata surfaced in the trace tab. */
export interface LaneTask {
  source: string;
  entities: string[];
  seedIds: string[];
  joinKey: string | null;
  rationale: string;
  limitsJson: string;
}

/** A compact evidence record as shown inside a specialist lane. */
export interface LaneRecord {
  id: string;
  accent: Accent;
  name: string;
  /** 1-based emission order within the specialist's result (arrival order). */
  order?: number;
  /** @deprecated kept for backwards compatibility with the static fixture; prefer fullJson */
  json: string;
  /** The entire EvidenceRecord pretty-printed as JSON. */
  fullJson: string;
  /** The provenance query that produced this record (provenance.query or ""). */
  query: string;
  /** Compact "dataset/backend · record_id · timestamp" provenance string, or "—". */
  provenanceMeta: string;
}

/** Live arrival metadata for one specialist lane, stamped client-side. */
export interface LaneArrival {
  subQuestion: string;
  /** Elapsed ms when the specialist-start event arrived (query began). */
  startedMs: number | null;
  /** Elapsed ms when the result event arrived (records landed). */
  arrivedMs: number | null;
  /** Seeds injected by dependent sequencing (0 for producers/independent). */
  seedCount: number;
  /** Producer sub-question id when this lane was a sequenced consumer. */
  producer: string | null;
  /** 1-based order this lane's result arrived in, among all results. */
  order: number | null;
}

/** One specialist lane (Cypher/neo4j or Gremlin/capec). */
export interface SpecialistLane {
  id: string;
  badge: string;
  backend: "neo4j" | "gremlin";
  accent: Accent;
  title: string;
  rows: number;
  ms: number;
  language: CodeLang;
  query: string;
  steps: MicroStep[];
  records: LaneRecord[];
  /** Live arrival metadata (null for demo turns / pre-integration payloads). */
  arrival?: LaneArrival | null;
  /** True for a synthesized in-flight lane (specialist started, no result yet). */
  placeholder?: boolean;
  /** Full task metadata for the task section. */
  task: LaneTask;
  /** All evaluator trace entries in order (includes gate/execute retries). */
  traceEntries: LaneTraceEntry[];
  /** Error message if the specialist failed, null otherwise. */
  error: string | null;
}

/** A reference to evidence, rendered as an inline provenance chip. */
export interface ProvenanceRef {
  id: string;
  source: string;
  accent: Accent;
  /** Inspector stage / record id this chip jumps to. */
  target?: string;
}

/** A run of plain text and inline chips / mono spans for the answer body. */
export type AnswerSegment =
  | { kind: "text"; text: string }
  | { kind: "chip"; ref: ProvenanceRef }
  | { kind: "mono"; text: string };

export interface AnswerParagraph {
  segments: AnswerSegment[];
}

/** A cross-source join pair shown as a connector chip. */
export interface JoinPair {
  left: string;
  leftAccent: Accent;
  right: string;
  rightAccent: Accent;
}

/** One verified-supported claim rendered in the answer card. */
export interface SynthesisClaimView {
  text: string;
  kind: "fact" | "correlation";
  /** Citation chips — one per (source, primary_id) the claim cites. */
  chips: ProvenanceRef[];
  /** The identifiers the sentence asserts (`entity_ids` on the backend claim).
   *  Carried through even where the UI doesn't yet display them so the network
   *  plot's edge-derivation has a stable id set to work from. */
  entityIds: string[];
}

/** A provenance-exact relationship for the network plot, projected from the
 *  backend `SynthesisEdge`. Present only on Option-B payloads; when empty the
 *  plot falls back to inferring edges. */
export interface SynthesisGraphEdge {
  source: string;
  target: string;
  rel: string;
}

/** One honest abstention rendered in the answer card. */
export interface SynthesisAbstentionView {
  source: string;
  accent: Accent;
  statement: string;
  /** The executed-query proof, or null for a schema-boundary refusal. */
  query: string | null;
}

/** A claim the verifier cut, kept visible as the audit trail. */
export interface FlaggedClaimView {
  text: string;
  reasons: string[];
}

/** UI-ready projection of the `answer.synthesis` payload. */
export interface SynthesisView {
  headline: string;
  /** The natural-language final answer shown above the claim table. */
  narrative: string;
  claims: SynthesisClaimView[];
  abstentions: SynthesisAbstentionView[];
  flagged: FlaggedClaimView[];
  notes: string[];
  composer: string;
  fallbackReason: string | null;
  verification: {
    supported: number;
    total: number;
    unsupportedRate: number;
    repairedAbstentions: number;
    ok: boolean;
  } | null;
  /** Provenance-exact network-plot edges (Option B). Empty on older payloads,
   *  in which case the plot infers edges from the join index + co-citation. */
  edges: SynthesisGraphEdge[];
}

export interface AnswerContent {
  paragraphs: AnswerParagraph[];
  joinPairs: JoinPair[];
  /** Verified synthesis view, or null when the payload predates Step 6. */
  synthesis: SynthesisView | null;
  /** Per-stage latency chips ("plan 12ms", …), or null when unavailable. */
  timings: { label: string; ms: number }[] | null;
  /** Human-readable dependent-sequencing notes (producer→consumer seeding). */
  sequencingNotes: string[];
}

/** A normalized evidence record row in the Evidence tab. */
export interface EvidenceRow {
  id: string;
  accent: Accent;
  label: string;
  name: string;
  meta: string;
  /** id_scheme from the original EvidenceRecord. */
  idScheme: string;
  /** Backend that produced this record (neo4j | gremlin). */
  backend: string;
  /** join_values from the original EvidenceRecord. */
  joinValues: string[];
  /** The provenance query, or null if no provenance. */
  provenanceQuery: string | null;
  /** Compact "dataset/backend · record_id · timestamp" string, or "—". */
  provenanceMeta: string;
  /** The ENTIRE EvidenceRecord pretty-printed as JSON. */
  fullJson: string;
}

/** A candidate in the Join Index tab. */
export interface JoinCandidate {
  left: string;
  leftAccent: Accent;
  right: string;
  rightAccent: Accent;
  matchedOn: string;
  confidence: "high" | "medium" | "low";
}

/** The aggregate a single assistant turn renders from. */
export interface WorkbenchRun {
  id: string;
  question: string;
  mode: "plan" | "query";
  drafter: "deterministic" | "llm";
  status: RunStatus;
  exitCode: ExitCode;
  elapsedMs: number;
  /** Wall-clock ms (Date.now) the turn was submitted; 0 for the seeded demo. */
  createdAt: number;
  liveSources: LiveSource[];
  stepper: MiniStep[];
  plannerStages: PlannerStage[];
  lanes: SpecialistLane[];
  answer: AnswerContent;
  evidence: EvidenceRow[];
  joinIndex: JoinCandidate[];
  joinKey: string;
  /** Canonical bundle for the Raw JSON tab — the real `to_dict()` shape. */
  federated: FederatedEvidence;
  /** Raw backend payloads retained verbatim for the Raw JSON tab (Phase 4). */
  rawProbe: ProbeSource[];
  rawPlan: Plan | null;
  rawAnswer: ServerAnswer | null;
  /** The literal ordered SSE event log for this turn — the pipeline start to finish. */
  events: StampedQueryEvent[];
  /** The conversational reply (from `final` / stored `payload.final_answer`), or
   *  null for turns predating the conversational path (e.g. offline demo turns). */
  reply?: ConversationalReply | null;
  /** Route decision for this turn ("quick" answered from memory, "graph" ran the
   *  federated pipeline), or null before the `route` event has arrived. */
  route?: "quick" | "graph" | null;
  /** Latest validation-gate verdict for this turn (retries surface the last one). */
  validation?: ValidationResult | null;
}

/** A sidebar conversation summary (view-model row). */
export interface ConversationSummary {
  id: string;
  title: string;
  mode: "plan" | "query";
  timeLabel: string;
  group: string;
  active?: boolean;
}

/* ============================================================
 * Persisted conversation threads (GET/POST/PATCH/DELETE /api/conversations)
 * ============================================================ */

/** `ConversationSummary` as the backend emits it (`api/models.py`). Named with
 *  a `DTO` suffix so it doesn't collide with the sidebar view-model above. */
export interface ConversationSummaryDTO {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  turn_count: number;
}

export interface ValidationResult {
  verdict: "pass" | "insufficient";
  reason: string;
  missing: string[];
  iteration: number;
  capped?: boolean;
}

/** One replayable transformed SSE event captured on a stored assistant turn. */
export interface StoredTurnEvent {
  type: string;
  data: unknown;
}

/** The assistant turn's stored payload (`api/services/conversations.py::_persist_turn`). */
export interface AssistantPayload {
  final_answer: string;
  route: "quick" | "graph";
  route_reason: string;
  resolved_question: string;
  validation: ValidationResult | null;
  facts: string[];
  status: string;
  exit_code: number;
  events: StoredTurnEvent[];
}

/** One turn (user or assistant) as stored/returned by `GET /api/conversations/{id}`. */
export interface StoredTurn {
  id: string;
  conversation_id: string;
  seq: number;
  role: "user" | "assistant";
  created_at: string;
  question: string | null;
  payload: AssistantPayload | null;
  mode: "plan" | "query" | null;
  drafter: "deterministic" | "llm" | null;
  route: "quick" | "graph" | null;
}

/** `GET /api/conversations/{id}` response: the summary plus all its turns. */
export interface ConversationDetailDTO extends ConversationSummaryDTO {
  turns: StoredTurn[];
}

/** The conversational reply rendered as the primary assistant bubble, projected
 *  from the `final` SSE event or a stored turn's `payload.final_answer`. */
export interface ConversationalReply {
  text: string;
  route: "quick" | "graph";
  composer: string;
  grounded: boolean;
}

/* ============================================================
 * API wire types (mirrors of the FastAPI service responses/events)
 * ============================================================ */

/** One backend in `GET /api/health`. */
export interface ApiLiveSource {
  backend: string;
  status: "live" | "down" | "starting";
  uri: string;
  nodes?: number | null;
  reason?: string | null;
}

/** Reachability of the synthesis LLM endpoint (drives the header LLM pill). */
export interface ApiLlmHealth {
  status: "live" | "down";
  base_url: string;
  model: string;
  enabled: boolean;
  reason?: string | null;
}

export interface ApiHealth {
  sources: ApiLiveSource[];
  docker: { available: boolean; services: Record<string, string>; reason?: string | null };
  llm: ApiLlmHealth;
  checked_at: string;
}

/** Resolved LLM settings for one agent in `GET /api/config`. */
export interface ApiLLMGroup {
  enabled: boolean;
  base_url: string;
  model: string;
  timeout_s: number;
  max_tokens: number;
}

/** Resolved LangGraph orchestration settings in `GET /api/config`. */
export interface ApiOrchestrationGroup {
  checkpointer: boolean;
  recursion_limit: number;
  pipeline_timeout_s: number;
}

export interface ApiConfig {
  llm: {
    planner: ApiLLMGroup;
    specialist: ApiLLMGroup;
    synthesis: ApiLLMGroup;
    eval: ApiLLMGroup;
  };
  connection: {
    neo4j_uri: string;
    neo4j_user: string;
    neo4j_password_set: boolean;
    gremlin_uri: string;
  };
  orchestration: ApiOrchestrationGroup;
}

/** Partial update body for `PUT /api/config`. */
export interface ApiConfigUpdate {
  planner?: Partial<Omit<ApiLLMGroup, never>>;
  specialist?: Partial<Omit<ApiLLMGroup, never>>;
  synthesis?: Partial<Omit<ApiLLMGroup, never>>;
  eval?: Partial<Omit<ApiLLMGroup, never>>;
  connection?: {
    neo4j_uri?: string;
    neo4j_user?: string;
    neo4j_password?: string;
    gremlin_uri?: string;
  };
  orchestration?: Partial<ApiOrchestrationGroup>;
}

/* -------------------------------------------------------------------------- */
/* Evaluation dashboard — mirrors utils/evaluation report JSON + SSE events.  */
/* -------------------------------------------------------------------------- */

/** A rate with a Wilson CI, as the report emits it. */
export interface RateCI {
  k: number;
  n: number;
  rate: number;
  ci_low: number;
  ci_high: number;
}

/** The `overall` block of the e2e report (utils/evaluation/score_e2e.aggregate). */
export interface E2EOverall {
  cross_source_accuracy: {
    positives: number;
    exact_match: RateCI;
    mean_precision: number;
    mean_recall: number;
    mean_f1: number;
    negatives: number;
    no_fabrication_rate: RateCI;
  };
  mapping_recall: {
    entries: number;
    gold_mappings: number;
    found_mappings: number;
    micro_recall: number;
    mean_recall: number;
  };
  provenance_correctness: {
    answers: number;
    mean_citation_provenance_rate: number;
    fully_provenanced: RateCI;
  };
  analyst_inspectability: {
    answers: number;
    mean_inspectability: number;
    mean_citation_coverage: number;
    mean_traceability: number;
    mean_abstention_proofs: number;
  };
  llm_judge: {
    source: string;
    llm_covered: number;
    answers_scored: number;
    mean_faithfulness: number;
    mean_groundedness: number;
    mean_evidence_sufficiency: number;
    mean_unsupported_claim_rate: number;
  };
}

export interface E2EReport {
  live: boolean;
  overall?: E2EOverall;
  by_tier?: Record<string, E2EOverall>;
  cases?: unknown[];
}

/** The full e2e report file (utils/evaluation/e2e_report.build_json). */
export interface E2EReportFile {
  meta: { attack_version: string; capec_version: string; generated_note: string };
  definitions: Record<string, string>;
  e2e: E2EReport;
  diagnosis: string[];
}

/** `GET /api/evaluation` response. */
export interface EvaluationReport {
  component_available: boolean;
  e2e_available: boolean;
  component: Record<string, unknown> | null;
  e2e: E2EReportFile | null;
}

/** SSE events streamed by `POST /api/eval-run`. */
export type EvalRunEvent =
  | { type: "status"; data: { message: string } }
  | { type: "log"; data: { line: string; level: string } }
  | { type: "done"; data: { ok: boolean; message: string; metrics?: Record<string, unknown> } };

/** One live source as emitted by the `probe` SSE event (richer than ApiLiveSource). */
export interface ProbeSource {
  dataset: string;
  backend: string;
  endpoint: string;
  live: boolean;
  node_count: number;
  observed_labels: string[];
  reason: string;
}

/** One section of the server-composed answer (`answer` SSE event). */
export interface ServerAnswerSection {
  source: string;
  backend: string;
  ok: boolean;
  partial: boolean;
  summary: string;
  record_ids: string[];
  record_count: number;
}

export interface ServerAnswerCross {
  value: string;
  entries: JoinIndexEntry[];
}

/* ------------------------------------------------------------------
 * Verified synthesis payload (`answer.synthesis`) — exact mirror of
 * utils/synthesis SynthesizedAnswer.to_dict() (Steps 6–7).
 * ------------------------------------------------------------------ */

export interface SynthesisCitation {
  source: string;
  primary_id: string;
  record_id: string;
}

export interface SynthesisVerdict {
  verdict: "supported" | "unsupported";
  reasons: string[];
}

export interface SynthesisClaim {
  text: string;
  citations: SynthesisCitation[];
  entity_ids: string[];
  kind: "fact" | "correlation";
  sub_question_id: string;
  /** Present on `claims` entries (null before verification); absent on `rendered_claims`. */
  verdict?: SynthesisVerdict | null;
}

/** An honest "the sources don't establish this". `query` is the executed-query
 *  proof — empty for a schema-boundary refusal where no query could express
 *  the question (e.g. ICS-only Assets against the Enterprise source). */
export interface SynthesisAbstention {
  sub_question_id: string;
  source: string;
  statement: string;
  query: string;
}

export interface SynthesisVerification {
  verdicts: SynthesisVerdict[];
  claim_count: number;
  supported_count: number;
  unsupported_count: number;
  unsupported_claim_rate: number;
  repaired_abstentions: number;
  ok: boolean;
}

export interface ServerSynthesisEdge {
  source_id: string;
  target_id: string;
  rel: string;
}

export interface ServerSynthesis {
  request: string;
  headline: string;
  /** Natural-language answer to the question. Optional: absent on pre-narrative payloads. */
  narrative?: string;
  claims: SynthesisClaim[];
  rendered_claims: SynthesisClaim[];
  abstentions: SynthesisAbstention[];
  notes: string[];
  composer: string;
  fallback_reason: string | null;
  verification: SynthesisVerification | null;
  /** Provenance-exact edges (Option B). Optional: absent on pre-edge payloads. */
  edges?: ServerSynthesisEdge[];
}

export interface ServerAnswer {
  headline: string;
  sections: ServerAnswerSection[];
  cross_source: ServerAnswerCross[];
  unsupported: UnsupportedPart[];
  /** Verified synthesis (Step 6+). Optional: absent on pre-Step-6 payloads. */
  synthesis?: ServerSynthesis | null;
  /** Per-stage pipeline latency (Wk 10–11+). Optional on older payloads. */
  timings?: PipelineTimings;
  status?: RunStatus;
  exit_code?: ExitCode;
}

/** The discriminated union of Server-Sent Events `POST /api/query` emits. */
/** Sufficiency verdict from the iterative-retrieval loop's `assess` node. */
export interface Assessment {
  sufficient: boolean;
  gaps: string[];
  missing_entities: string[];
  hop: number;
  hop_capped: boolean;
  mode: string;
  reason: string;
}

export type QueryEvent =
  // `hop`/`added` ride on the re-plan status frame the loop emits between hops.
  | { type: "status"; data: { phase: string; message?: string; count?: number; hop?: number; added?: number } }
  | { type: "probe"; data: { live_sources: ProbeSource[] } }
  | { type: "plan"; data: { plan: Plan; target_sources: string[] } }
  | {
      type: "specialist-start";
      data: {
        sub_question: string;
        source: string;
        index: number;
        total: number;
        seed_count: number;
        producer: string | null;
        skipped: string | null;
      };
    }
  | { type: "specialist"; data: { result: SpecialistResult; index: number; total: number } }
  | { type: "skipped"; data: { sub_question: string; source: string; reason: string } }
  | { type: "evidence"; data: { evidence: FederatedEvidence } }
  | { type: "assess"; data: { assessment: Assessment; hop: number; max_hops: number } }
  | { type: "answer"; data: ServerAnswer }
  | { type: "done"; data: { status: RunStatus; exit_code: ExitCode; message?: string; timings?: PipelineTimings } }
  | { type: "error"; data: { message: string } }
  | { type: "context"; data: { resolved_question: string; rewritten: boolean } }
  | { type: "route"; data: { decision: "quick" | "graph"; reason: string } }
  | {
      type: "validation";
      data: {
        verdict: "pass" | "insufficient";
        reason: string;
        missing: string[];
        iteration: number;
        capped?: boolean;
      };
    }
  | {
      type: "final";
      data: { final_answer: string; route: "quick" | "graph"; composer: "llm" | "deterministic"; grounded: boolean };
    }
  | { type: "conversation"; data: { conversation_id: string; title?: string } };

export type QueryEventType = QueryEvent["type"];

/** A captured SSE event stamped with elapsed-ms at browser arrival. */
export type StampedQueryEvent = QueryEvent & { receivedMs?: number };

/** Admin (infra/data/graph) action request body for `POST /api/admin`. */
export type AdminAction =
  | "docker-status"
  | "docker-start"
  | "docker-stop"
  | "graph-health"
  | "graph-load"
  | "graph-verify"
  | "graph-stop"
  | "data-download"
  | "data-build"
  | "yolo-all";

export interface AdminActionBody {
  action: AdminAction;
  dataset?: "attack" | "capec" | "all";
  graph?: "neo4j" | "gremlin" | "all";
  force?: boolean;
  dry_run?: boolean;
}

/* ============================================================
 * Graph API types (GET /api/graph/{dataset})
 * ============================================================ */

export type GraphDataset = "attack" | "capec";

export interface GraphNode {
  id: string;
  label: string;
  labels: string[];
  name: string;
  properties: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
}

export interface GraphPayload {
  dataset: string;
  backend: string;
  counts: { nodes: number; relationships: number };
  nodes_by_label: Record<string, number>;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

/** SSE events streamed by `POST /api/admin`. */
export type AdminEvent =
  | { type: "status"; data: { action: string; message?: string } }
  | { type: "log"; data: { line: string; level: string } }
  | { type: "done"; data: { ok: boolean; message: string } & Record<string, unknown> };
