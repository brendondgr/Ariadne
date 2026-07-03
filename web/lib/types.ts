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

export interface FederatedEvidence {
  request: string;
  results: SpecialistResult[];
  unsupported: UnsupportedPart[];
  skipped: Record<string, unknown>[];
  partial: boolean;
  join_index: Record<string, JoinIndexEntry[]>;
  cross_source_join_values: string[];
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
  /** @deprecated kept for backwards compatibility with the static fixture; prefer fullJson */
  json: string;
  /** The entire EvidenceRecord pretty-printed as JSON. */
  fullJson: string;
  /** The provenance query that produced this record (provenance.query or ""). */
  query: string;
  /** Compact "dataset/backend · record_id · timestamp" provenance string, or "—". */
  provenanceMeta: string;
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

export interface AnswerContent {
  paragraphs: AnswerParagraph[];
  joinPairs: JoinPair[];
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
  events: QueryEvent[];
}

/** A sidebar conversation summary. */
export interface ConversationSummary {
  id: string;
  title: string;
  mode: "plan" | "query";
  timeLabel: string;
  group: string;
  active?: boolean;
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

export interface ApiHealth {
  sources: ApiLiveSource[];
  docker: { available: boolean; services: Record<string, string>; reason?: string | null };
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

export interface ApiConfig {
  llm: { planner: ApiLLMGroup; specialist: ApiLLMGroup };
  connection: {
    neo4j_uri: string;
    neo4j_user: string;
    neo4j_password_set: boolean;
    gremlin_uri: string;
  };
}

/** Partial update body for `PUT /api/config`. */
export interface ApiConfigUpdate {
  planner?: Partial<Omit<ApiLLMGroup, never>>;
  specialist?: Partial<Omit<ApiLLMGroup, never>>;
  connection?: {
    neo4j_uri?: string;
    neo4j_user?: string;
    neo4j_password?: string;
    gremlin_uri?: string;
  };
}

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

export interface ServerAnswer {
  headline: string;
  sections: ServerAnswerSection[];
  cross_source: ServerAnswerCross[];
  unsupported: UnsupportedPart[];
  status?: RunStatus;
  exit_code?: ExitCode;
}

/** The discriminated union of Server-Sent Events `POST /api/query` emits. */
export type QueryEvent =
  | { type: "status"; data: { phase: string; message?: string; count?: number } }
  | { type: "probe"; data: { live_sources: ProbeSource[] } }
  | { type: "plan"; data: { plan: Plan; target_sources: string[] } }
  | { type: "specialist"; data: { result: SpecialistResult; index: number; total: number } }
  | { type: "skipped"; data: { sub_question: string; source: string; reason: string } }
  | { type: "evidence"; data: { evidence: FederatedEvidence } }
  | { type: "answer"; data: ServerAnswer }
  | { type: "done"; data: { status: RunStatus; exit_code: ExitCode; message?: string } }
  | { type: "error"; data: { message: string } };

export type QueryEventType = QueryEvent["type"];

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
