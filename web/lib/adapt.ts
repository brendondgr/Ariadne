/**
 * Adapter: backend payloads → the {@link WorkbenchRun} view-model.
 *
 * The components are a pure function of `WorkbenchRun`; this module is the only
 * place that knows how the FastAPI service's `to_dict()` shapes (Plan,
 * FederatedEvidence, the probe/answer SSE payloads) map onto the UI types. Every
 * builder is a pure function so the run machine (see `runMachine.ts`) can call
 * them incrementally as events stream in, and `buildRun` assembles the final
 * turn for tests and the completed state.
 */

import type {
  Accent,
  AnswerContent,
  AnswerParagraph,
  AnswerSegment,
  CodeLang,
  ConversationalReply,
  EvidenceRow,
  ExitCode,
  FederatedEvidence,
  JoinCandidate,
  JoinIndexEntry,
  JoinPair,
  LaneRecord,
  LaneTask,
  LaneTraceEntry,
  LiveSource,
  MicroStep,
  MiniStep,
  PipelineTimings,
  Plan,
  PlannerStage,
  ProbeSource,
  LaneArrival,
  StampedQueryEvent,
  RunStatus,
  ServerAnswer,
  ServerAnswerCross,
  ServerSynthesis,
  SpecialistLane,
  SpecialistResult,
  SpecialistStep,
  StageStatus,
  SynthesisView,
  ValidationResult,
  WorkbenchRun,
} from "./types";

/* ----------------------------- small helpers ----------------------------- */

const BACKEND_ACCENT: Record<string, Accent> = { neo4j: "teal", gremlin: "amber" };
const SOURCE_BACKEND: Record<string, "neo4j" | "gremlin"> = { attack: "neo4j", capec: "gremlin" };

function backendOf(result: SpecialistResult): "neo4j" | "gremlin" {
  const prov = result.records.find((r) => r.provenance)?.provenance;
  if (prov?.backend === "neo4j" || prov?.backend === "gremlin") return prov.backend;
  return SOURCE_BACKEND[result.task.source] ?? "neo4j";
}

function accentOf(backend: string): Accent {
  return BACKEND_ACCENT[backend] ?? "sage";
}

function accentForSource(source?: string): Accent {
  return source ? accentOf(SOURCE_BACKEND[source] ?? "neo4j") : "sage";
}

function langOf(backend: "neo4j" | "gremlin"): CodeLang {
  return backend === "neo4j" ? "cypher" : "gremlin";
}

function deriveJoinKey(plan: Plan | null): string {
  if (plan?.joins?.length) return plan.joins[0].on || plan.joins[0].key;
  const sq = plan?.sub_questions.find((s) => s.join_key);
  return sq?.join_key ?? "external_id";
}

function unique(values: string[]): string[] {
  return Array.from(new Set(values));
}

/* ------------------------------ live sources ------------------------------ */

export function buildLiveSources(probe: ProbeSource[]): LiveSource[] {
  return probe.map((s) => ({
    backend: s.backend,
    status: s.live ? "live" : "down",
    nodes: s.node_count,
    reason: s.live ? undefined : s.reason,
  }));
}

/* ----------------------------- planner stages ----------------------------- */

export function buildPlannerStages(
  plan: Plan,
  probe: ProbeSource[],
  drafter: "deterministic" | "llm",
): PlannerStage[] {
  const liveSources = buildLiveSources(probe);
  const anyLive = probe.some((s) => s.live);

  const probeCode = JSON.stringify(
    Object.fromEntries(
      probe.map((s) => [s.backend, { status: s.live ? "live" : "down", nodes: s.node_count }]),
    ),
    null,
    2,
  );
  const probeSummary =
    probe
      .map((s) => `${s.backend} ${s.live ? "LIVE" : "DEAD"} · ${s.live ? s.node_count.toLocaleString() : "—"}`)
      .join(" · ") || "no sources probed";

  const lastTrace = plan.trace.length ? plan.trace[plan.trace.length - 1] : null;
  const gateOk = lastTrace ? lastTrace.gate_ok : !plan.partial;
  const joinKey = deriveJoinKey(plan);
  const entities = unique(plan.sub_questions.flatMap((sq) => sq.entities)).slice(0, 6);

  return [
    {
      id: "stage-probe",
      index: "①",
      title: "Probe live sources",
      status: anyLive ? "pass" : "fail",
      summary: probeSummary,
      liveSources,
      code: `# live_sources()\n${probeCode}`,
      codeLang: "json",
    },
    {
      id: "stage-draft",
      index: "②",
      title: "Draft plan",
      status: "pass",
      summary: `drafter ${drafter} · ${plan.sub_questions.length} sub-question(s) proposed`,
      code: `# proposed sub-questions\n${JSON.stringify(
        plan.sub_questions.map((sq) => ({
          id: sq.id,
          source: sq.source,
          text: sq.text,
          entities: sq.entities,
          join_key: sq.join_key,
          rationale: sq.rationale,
        })),
        null,
        2,
      )}`,
      codeLang: "json",
    },
    {
      id: "stage-gate",
      index: "③",
      title: "Plan gate",
      status: gateOk ? "pass" : "partial",
      summary: gateOk
        ? `passed · ${plan.trace.length || 1} iteration(s)`
        : `${lastTrace?.reasons.length ?? 0} rejection(s) · ${plan.trace.length || 1} iteration(s)`,
      shield: true,
      tag: drafter,
      code: `# plan gate iterations\n${JSON.stringify(plan.trace, null, 2)}`,
      codeLang: "json",
      codeEmphasis: true,
    },
    {
      id: "stage-emit",
      index: "④",
      title: "Emit plan",
      status: plan.partial ? "partial" : "pass",
      summary: `entities [${entities.join(", ")}] · join key ${joinKey}`,
      code: JSON.stringify(
        {
          joins: plan.joins.map((j) => ({ key: j.key, sources: j.sources, on: j.on })),
          unsupported: plan.unsupported.map((u) => ({ description: u.description, reason: u.reason })),
          assumptions: plan.assumptions,
          rationale: plan.rationale,
        },
        null,
        2,
      ),
      codeLang: "json",
    },
  ];
}

/* ------------------------------- lanes ------------------------------------ */

/** Six canonical specialist checkpoints in order — no draft, no handoff. */
const UI_STEPS: { key: SpecialistStep; label: string }[] = [
  { key: "intake", label: "intake" },
  { key: "resolve", label: "resolve" },
  { key: "gate", label: "pre-run gate" },
  { key: "execute", label: "execute" },
  { key: "assess", label: "assess" },
  { key: "normalize", label: "normalize" },
];

function stepLabel(step: SpecialistStep): string {
  const found = UI_STEPS.find((s) => s.key === step);
  return found ? found.label : step;
}

function laneSteps(result: SpecialistResult): MicroStep[] {
  // For the deduped pill row, use the LAST trace for each canonical step.
  const byStep = new Map<SpecialistStep, (typeof result.traces)[0]>();
  for (const t of result.traces) {
    byStep.set(t.step, t);
  }
  const fallback: StageStatus = result.ok ? "pass" : result.partial ? "partial" : "fail";
  return UI_STEPS.map(({ key, label }) => {
    const trace = byStep.get(key);
    const status: StageStatus = trace ? (trace.ok ? "pass" : "fail") : fallback;
    return { key, label, status, emphasis: key === "gate" || key === "normalize" };
  });
}

/** Build all evaluator trace entries in order, INCLUDING repeats (gate/execute retries). */
export function buildTraceEntries(result: SpecialistResult): LaneTraceEntry[] {
  const fallback: StageStatus = result.ok ? "pass" : result.partial ? "partial" : "fail";
  if (!result.traces || result.traces.length === 0) {
    return UI_STEPS.map(({ key, label }) => ({
      step: key,
      label,
      status: fallback,
      emphasis: key === "gate" || key === "normalize",
      reasons: [],
      detailJson: "{}",
    }));
  }
  return result.traces.map((t) => ({
    step: t.step,
    label: stepLabel(t.step),
    status: t.ok ? "pass" : "fail",
    emphasis: t.step === "gate" || t.step === "normalize",
    reasons: t.reasons,
    detailJson: JSON.stringify(t.detail, null, 2),
  }));
}

/** Build per-specialist task metadata for the Task section. */
export function buildLaneTask(task: SpecialistResult["task"]): LaneTask {
  return {
    source: task.source,
    entities: task.entities,
    seedIds: task.seed_ids,
    joinKey: task.join_key,
    rationale: task.rationale,
    limitsJson: JSON.stringify(task.limits, null, 2),
  };
}

function laneMs(result: SpecialistResult): number {
  const exec = result.traces.find((t) => t.step === "execute");
  const ms = exec?.detail?.["timing_ms"];
  return typeof ms === "number" ? ms : 0;
}

function buildProvenanceMeta(prov: import("./types").Provenance | null | undefined): string {
  if (!prov) return "—";
  const ts = prov.timestamp ? prov.timestamp.replace("T", " ").replace(/\.\d+Z$/, "Z") : "—";
  return `${prov.dataset}/${prov.backend} · ${prov.record_id} · ${ts}`;
}

function compactRecordJson(label: string, joinValues: string[], provLabel: string): string {
  return `{ "label":"${label}", "join_values":${JSON.stringify(joinValues)},\n  "provenance":"${provLabel}" }`;
}

export function buildLane(
  result: SpecialistResult,
  arrival: LaneArrival | null = null,
): SpecialistLane {
  const backend = backendOf(result);
  const accent = accentOf(backend);
  // ALL records — no cap
  const records: LaneRecord[] = result.records.map((rec, i) => ({
    id: rec.primary_id || rec.name || "record",
    accent,
    name: rec.name,
    order: i + 1,
    // Keep legacy json field for backwards compat with static fixture
    json: compactRecordJson(
      rec.label,
      rec.join_values,
      rec.provenance ? `${rec.provenance.dataset} / ${rec.provenance.backend}` : backend,
    ),
    fullJson: JSON.stringify(rec, null, 2),
    query: rec.provenance?.query ?? "",
    provenanceMeta: buildProvenanceMeta(rec.provenance),
  }));
  return {
    id: `lane-${backend}`,
    badge: `${backend === "neo4j" ? "Cypher" : "Gremlin"} · ${result.task.source}`,
    backend,
    accent,
    title: result.task.text || `${result.task.source} specialist`,
    rows: result.record_count,
    ms: laneMs(result),
    language: langOf(backend),
    query: result.query,
    steps: laneSteps(result),
    records,
    task: buildLaneTask(result.task),
    traceEntries: buildTraceEntries(result),
    arrival,
    error: result.error ?? null,
  };
}

/* ------------------------------- answer ----------------------------------- */

function buildJoinPairs(cross: ServerAnswerCross[]): JoinPair[] {
  return cross.slice(0, 12).map((c) => {
    const left = c.entries.find((e) => e.source === "capec") ?? c.entries[0];
    const right =
      c.entries.find((e) => e.source === "attack") ?? c.entries[1] ?? c.entries[0];
    return {
      left: left?.primary_id ?? c.value,
      leftAccent: accentForSource(left?.source),
      right: right?.primary_id ?? c.value,
      rightAccent: accentForSource(right?.source),
    };
  });
}

/** Project the verified `answer.synthesis` payload into its UI view.
 *
 *  Renders only what the verifier let through: `rendered_claims` (supported)
 *  become cited claims, unsupported claims surface in `flagged` with the
 *  verdict reasons, and abstentions keep their proof shape — the executed
 *  query, or `query: null` for a schema-boundary refusal (Step 7) where no
 *  query could express the question. */
export function buildSynthesis(synthesis: ServerSynthesis | null | undefined): SynthesisView | null {
  if (!synthesis) return null;

  const claims = synthesis.rendered_claims.map((claim) => ({
    text: claim.text,
    kind: claim.kind,
    chips: claim.citations.map((c) => {
      const backend = SOURCE_BACKEND[c.source] ?? "neo4j";
      return {
        id: c.primary_id,
        source: `${c.source}/${backend}`,
        accent: accentForSource(c.source),
        target: `lane-${backend}`,
      };
    }),
    entityIds: [...claim.entity_ids],
    contested: [...(claim.contested ?? [])],
  }));

  const abstentions = synthesis.abstentions.map((a) => ({
    source: a.source,
    accent: accentForSource(a.source),
    statement: a.statement,
    query: a.query || null,
  }));

  const flagged = synthesis.claims
    .filter((claim) => claim.verdict && claim.verdict.verdict !== "supported")
    .map((claim) => ({ text: claim.text, reasons: claim.verdict?.reasons ?? [] }));

  const edges = (synthesis.edges ?? []).map((e) => ({
    source: e.source_id,
    target: e.target_id,
    rel: e.rel,
  }));

  const report = synthesis.verification;
  const conflicts = (report?.conflicts ?? []).map((c) => ({
    joinValue: c.join_value,
    kind: c.kind,
    detail: c.detail,
    values: Object.entries(c.values)
      .map(([source, value]) => ({
        source,
        accent: accentForSource(source),
        value,
        authoritative: source === c.authoritative_source,
      }))
      .sort((a, b) => a.source.localeCompare(b.source)),
  }));

  return {
    headline: synthesis.headline,
    narrative: synthesis.narrative ?? "",
    claims,
    abstentions,
    flagged,
    conflicts,
    edges,
    notes: synthesis.notes,
    composer: synthesis.composer,
    fallbackReason: synthesis.fallback_reason,
    verification: report
      ? {
          supported: report.supported_count,
          total: report.claim_count,
          unsupportedRate: report.unsupported_claim_rate,
          repairedAbstentions: report.repaired_abstentions,
          ok: report.ok,
          conflictCount: report.conflict_count ?? (report.conflicts?.length ?? 0),
        }
      : null,
  };
}

/** Project the pipeline's per-stage timings into ordered latency chips. */
export function buildTimings(timings: PipelineTimings | null | undefined): AnswerContent["timings"] {
  if (!timings) return null;
  const chips: { label: string; ms: number }[] = [];
  if (timings.plan_ms !== undefined) chips.push({ label: "plan", ms: timings.plan_ms });
  for (const s of timings.specialists ?? []) chips.push({ label: s.source, ms: s.ms });
  if (timings.synthesis_ms !== undefined) chips.push({ label: "synthesis", ms: timings.synthesis_ms });
  if (timings.total_ms !== undefined) chips.push({ label: "total", ms: timings.total_ms });
  return chips.length ? chips : null;
}

/** Human-readable dependent-sequencing notes from the evidence audit trail. */
export function buildSequencingNotes(evidence: FederatedEvidence | null): string[] {
  return (evidence?.sequencing ?? []).map((s) =>
    s.skipped
      ? `${s.consumer} skipped — producer ${s.producer}: ${s.skipped}`
      : `${s.consumer} seeded with ${s.seed_count} join value(s) from ${s.producer}` +
        (s.truncated ? " (truncated)" : ""),
  );
}

export function buildAnswer(
  answer: ServerAnswer | null,
  joinKey: string,
  evidence: FederatedEvidence | null = null,
): AnswerContent {
  if (!answer)
    return { paragraphs: [], joinPairs: [], synthesis: null, timings: null, sequencingNotes: [] };

  const paragraphs: AnswerParagraph[] = [];
  if (answer.headline) paragraphs.push({ segments: [{ kind: "text", text: answer.headline }] });

  for (const section of answer.sections) {
    const accent = accentOf(section.backend);
    const segments: AnswerSegment[] = [
      { kind: "text", text: section.summary + (section.record_ids.length ? "  " : "") },
    ];
    section.record_ids.forEach((id, i) => {
      segments.push({
        kind: "chip",
        ref: { id, source: `${section.source}/${section.backend}`, accent, target: `lane-${section.backend}` },
      });
      if (i < section.record_ids.length - 1) segments.push({ kind: "text", text: ", " });
    });
    paragraphs.push({ segments });
  }

  if (answer.cross_source.length) {
    paragraphs.push({
      segments: [
        { kind: "text", text: "Cross-source correlation on shared " },
        { kind: "mono", text: joinKey },
        { kind: "text", text: `: ${answer.cross_source.length} shared identifier(s).` },
      ],
    });
  }

  if (answer.unsupported?.length) {
    paragraphs.push({
      segments: [
        {
          kind: "text",
          text: `Unsupported: ${answer.unsupported.map((u) => u.description).join("; ")}.`,
        },
      ],
    });
  }

  return {
    paragraphs,
    joinPairs: buildJoinPairs(answer.cross_source),
    synthesis: buildSynthesis(answer.synthesis),
    timings: buildTimings(answer.timings),
    sequencingNotes: buildSequencingNotes(evidence),
  };
}

/* --------------------------- evidence + join tabs ------------------------- */

export function buildEvidenceRows(evidence: FederatedEvidence): EvidenceRow[] {
  const rows: EvidenceRow[] = [];
  for (const result of evidence.results) {
    const backend = backendOf(result);
    const accent = accentOf(backend);
    // ALL records — no cap
    for (const rec of result.records) {
      const prov = rec.provenance;
      rows.push({
        id: rec.primary_id || rec.name,
        accent,
        label: rec.label,
        name: rec.name,
        meta: `join_values: ${JSON.stringify(rec.join_values)} · ${
          prov ? `${prov.dataset} / ${prov.backend}` : "—"
        }`,
        idScheme: rec.id_scheme,
        backend,
        joinValues: rec.join_values,
        provenanceQuery: rec.provenance?.query ?? null,
        provenanceMeta: buildProvenanceMeta(rec.provenance),
        fullJson: JSON.stringify(rec, null, 2),
      });
    }
  }
  return rows;
}

function pairFromEntries(entries: JoinIndexEntry[], value: string) {
  const left = entries.find((e) => e.source === "capec") ?? entries[0];
  const right = entries.find((e) => e.source === "attack") ?? entries[1] ?? entries[0];
  return {
    left: left?.primary_id ?? value,
    leftAccent: accentForSource(left?.source),
    right: right?.primary_id ?? value,
    rightAccent: accentForSource(right?.source),
  };
}

export function buildJoinIndex(evidence: FederatedEvidence, joinKey: string): JoinCandidate[] {
  return evidence.cross_source_join_values.slice(0, 200).map((value) => {
    const pair = pairFromEntries(evidence.join_index[value] ?? [], value);
    return { ...pair, matchedOn: joinKey, confidence: "high" as const };
  });
}

/* ------------------------------- stepper ---------------------------------- */

function buildStepper(
  plan: Plan | null,
  evidence: FederatedEvidence | null,
  liveSources: LiveSource[],
  status: RunStatus,
): MiniStep[] {
  const anyLive = liveSources.some((s) => s.status === "live");
  const planStatus: StageStatus = plan ? (plan.partial ? "partial" : "pass") : "pending";
  const specStatus: StageStatus = evidence
    ? evidence.results.length === 0
      ? "fail"
      : evidence.results.every((r) => r.ok) && !evidence.partial
        ? "pass"
        : "partial"
    : "pending";
  const evidenceStatus: StageStatus = evidence ? (evidence.partial ? "partial" : "pass") : "pending";
  const answerStatus: StageStatus =
    status === "answered" ? "pass" : status === "partial" ? "partial" : status === "no_sources" ? "fail" : "pending";
  const firstLane = evidence?.results[0] ? `lane-${backendOf(evidence.results[0])}` : "stage-gate";

  // Planner step one is its own visible step: it has run once a plan exists.
  const classifyStatus: StageStatus = plan ? "pass" : "pending";

  return [
    { key: "probe", label: "Probe", status: anyLive ? "pass" : "fail", target: "stage-probe" },
    { key: "classify", label: "Intent", status: classifyStatus, target: "stage-draft" },
    { key: "plan", label: "Plan", status: planStatus, target: "stage-gate" },
    { key: "specialists", label: "Specialists", status: specStatus, target: firstLane },
    { key: "evidence", label: "Evidence", status: evidenceStatus, target: "stage-emit" },
    { key: "answer", label: "Answer", status: answerStatus, target: "stage-emit" },
  ];
}

/* --------------------------------- buildRun ------------------------------- */

export interface RunInputs {
  id: string;
  question: string;
  mode: "plan" | "query";
  drafter: "deterministic" | "llm";
  liveSources: ProbeSource[];
  plan: Plan | null;
  evidence: FederatedEvidence | null;
  answer: ServerAnswer | null;
  status: RunStatus;
  exitCode: ExitCode;
  elapsedMs: number;
  /** Wall-clock submit time; optional so existing callers/tests need no change. */
  createdAt?: number;
  /** The ordered SSE event log captured for this turn (Raw JSON event stream). */
  events?: StampedQueryEvent[];
  /** Live arrival metadata per lane id ("lane-neo4j"/"lane-gremlin"). */
  laneMeta?: Record<string, LaneArrival>;
  /** The conversational reply (from `final` / stored `payload.final_answer`). */
  reply?: ConversationalReply | null;
  /** Route decision for this turn ("quick" | "graph"), from the `route` event. */
  route?: "quick" | "graph" | null;
  /** Latest validation-gate verdict (retries overwrite with the last one). */
  validation?: ValidationResult | null;
}

function emptyEvidence(request: string): FederatedEvidence {
  return {
    request,
    results: [],
    unsupported: [],
    skipped: [],
    partial: false,
    join_index: {},
    cross_source_join_values: [],
  };
}

/** Assemble a complete {@link WorkbenchRun} from collected backend payloads. */
/** Lanes from returned results, plus in-flight placeholders while streaming:
 *  a routed sub-question with no result yet renders as a live "querying…"
 *  shimmer lane (only while the run status is still "running"). */
function buildLanes(inputs: RunInputs, evidence: FederatedEvidence | null) {
  const lanes = (evidence?.results ?? []).map((r) =>
    buildLane(r, inputs.laneMeta?.[`lane-${backendOf(r)}`] ?? null),
  );
  if (inputs.status !== "running" || !inputs.plan) return lanes;
  const have = new Set(lanes.map((l) => l.id));
  for (const sq of inputs.plan.sub_questions) {
    const backend: "neo4j" | "gremlin" = sq.source === "capec" ? "gremlin" : "neo4j";
    const id = `lane-${backend}`;
    if (have.has(id)) continue;
    have.add(id);
    lanes.push({
      id,
      badge: `${backend === "neo4j" ? "Cypher" : "Gremlin"} · ${sq.source}`,
      backend,
      accent: accentOf(backend),
      title: sq.text || `${sq.source} specialist`,
      rows: 0,
      ms: 0,
      language: langOf(backend),
      query: "",
      steps: [],
      records: [],
      task: {
        source: sq.source,
        entities: sq.entities ?? [],
        seedIds: [],
        joinKey: sq.join_key ?? null,
        rationale: sq.rationale ?? "",
        limitsJson: JSON.stringify(sq.limits ?? {}),
      },
      traceEntries: [],
      arrival: inputs.laneMeta?.[id] ?? null,
      error: null,
      placeholder: true,
    });
  }
  return lanes;
}

export function buildRun(inputs: RunInputs): WorkbenchRun {
  const { id, question, mode, drafter, liveSources: probe, plan, evidence, answer, status, exitCode, elapsedMs } = inputs;
  const joinKey = deriveJoinKey(plan);
  const wbLive = buildLiveSources(probe);

  return {
    id,
    question,
    mode,
    drafter,
    status,
    exitCode,
    elapsedMs,
    createdAt: inputs.createdAt ?? 0,
    liveSources: wbLive,
    stepper: buildStepper(plan, evidence, wbLive, status),
    plannerStages: plan ? buildPlannerStages(plan, probe, drafter) : [],
    lanes: buildLanes(inputs, evidence),
    answer: buildAnswer(answer, joinKey, evidence),
    evidence: evidence ? buildEvidenceRows(evidence) : [],
    joinIndex: evidence ? buildJoinIndex(evidence, joinKey) : [],
    joinKey,
    federated: evidence ?? emptyEvidence(question),
    // Raw payloads kept verbatim for the Raw JSON tab + the literal event log.
    rawProbe: probe,
    rawPlan: plan,
    rawAnswer: answer,
    events: inputs.events ?? [],
    reply: inputs.reply ?? null,
    route: inputs.route ?? null,
    validation: inputs.validation ?? null,
  };
}
