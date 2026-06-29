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

/** The eight checkpoints of the specialist loop, in order. */
export type SpecialistStep =
  | "intake"
  | "resolve"
  | "draft"
  | "gate"
  | "execute"
  | "assess"
  | "normalize"
  | "handoff";

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

/** A single one of the eight specialist micro-steps. */
export interface MicroStep {
  key: SpecialistStep;
  label: string;
  status: StageStatus;
  /** The two never-cut checkpoints (pre-run gate, normalize) get emphasis. */
  emphasis?: boolean;
}

/** A compact evidence record as shown inside a specialist lane. */
export interface LaneRecord {
  id: string;
  accent: Accent;
  name: string;
  json: string;
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
