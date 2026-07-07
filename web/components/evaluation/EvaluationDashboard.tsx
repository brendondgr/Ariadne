"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { E2EOverall, E2EReportFile, EvaluationReport } from "@/lib/types";
import { getEvaluation, streamEvalRun } from "@/lib/api";
import { MetricCard } from "./MetricCard";
import { JudgePanel } from "./JudgePanel";

/** Format a 0–1 rate as a percentage string. */
function pct(x: number | undefined): string {
  return x === undefined ? "—" : `${(x * 100).toFixed(1)}%`;
}

/**
 * Evaluation view: reads the committed component + e2e reports from
 * `GET /api/evaluation` (always available — served from disk, no stack needed)
 * and renders the four end-to-end metrics plus the LLM-judge panel. A "Run
 * evaluation" button re-runs the pipeline scorer live via SSE and refreshes.
 */
export function EvaluationDashboard() {
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  const [running, setRunning] = useState(false);
  const [runLog, setRunLog] = useState<string[]>([]);
  const [judge, setJudge] = useState(false);
  const runAbort = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await getEvaluation(controller.signal);
        if (!controller.signal.aborted) {
          setReport(data);
          setLoading(false);
        }
      } catch (err: unknown) {
        if ((err as { name?: string }).name === "AbortError") return;
        setError(err instanceof Error ? err.message : String(err));
        setLoading(false);
      }
    }
    void load();
    return () => controller.abort();
  }, [retryKey]);

  const handleRun = useCallback(() => {
    runAbort.current?.abort();
    const controller = new AbortController();
    runAbort.current = controller;
    setRunning(true);
    setRunLog(["Starting end-to-end evaluation…"]);

    void streamEvalRun(
      { live: true, judge },
      (event) => {
        if (event.type === "status") {
          setRunLog((l) => [...l, event.data.message]);
        } else if (event.type === "log") {
          setRunLog((l) => [...l.slice(-200), event.data.line]);
        } else if (event.type === "done") {
          setRunLog((l) => [...l, event.data.message]);
          setRunning(false);
          setRetryKey((k) => k + 1); // refresh the committed report
        }
      },
      controller.signal,
    ).catch((err: unknown) => {
      if ((err as { name?: string }).name === "AbortError") return;
      setRunLog((l) => [...l, `error: ${err instanceof Error ? err.message : String(err)}`]);
      setRunning(false);
    });
  }, [judge]);

  const file: E2EReportFile | null = report?.e2e ?? null;
  const overall: E2EOverall | undefined = file?.e2e.live ? file.e2e.overall : undefined;

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <SecondaryNav
        note={file?.meta.generated_note}
        running={running}
        judge={judge}
        onToggleJudge={() => setJudge((j) => !j)}
        onRun={handleRun}
      />

      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
        {loading && <Centered>Loading evaluation report…</Centered>}
        {!loading && error && <ErrorCard message={error} onRetry={() => setRetryKey((k) => k + 1)} />}

        {!loading && !error && report && (
          <div className="mx-auto flex max-w-5xl flex-col gap-6">
            {running && <RunLog lines={runLog} />}

            {overall ? (
              <>
                <section className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <MetricCard
                    title="Cross-source answer accuracy"
                    value={pct(overall.cross_source_accuracy.exact_match.rate)}
                    caption={`exact-set-match over ${overall.cross_source_accuracy.exact_match.n} federated positives`}
                    stats={[
                      ["precision", overall.cross_source_accuracy.mean_precision.toFixed(3)],
                      ["recall", overall.cross_source_accuracy.mean_recall.toFixed(3)],
                      ["F1", overall.cross_source_accuracy.mean_f1.toFixed(3)],
                      ["no-fabrication (neg)", pct(overall.cross_source_accuracy.no_fabrication_rate.rate)],
                    ]}
                  />
                  <MetricCard
                    title="CAPEC→ATT&CK mapping recall"
                    value={pct(overall.mapping_recall.micro_recall)}
                    caption={`${overall.mapping_recall.found_mappings}/${overall.mapping_recall.gold_mappings} gold mappings surfaced`}
                    stats={[
                      ["entries", String(overall.mapping_recall.entries)],
                      ["mean per-entry", pct(overall.mapping_recall.mean_recall)],
                    ]}
                  />
                  <MetricCard
                    title="Provenance correctness"
                    value={pct(overall.provenance_correctness.fully_provenanced.rate)}
                    caption={`fully-provenanced answers of ${overall.provenance_correctness.answers}`}
                    stats={[
                      ["mean citation rate", pct(overall.provenance_correctness.mean_citation_provenance_rate)],
                    ]}
                  />
                  <MetricCard
                    title="Analyst inspectability"
                    value={pct(overall.analyst_inspectability.mean_inspectability)}
                    caption={`composite over ${overall.analyst_inspectability.answers} answers`}
                    stats={[
                      ["citation coverage", pct(overall.analyst_inspectability.mean_citation_coverage)],
                      ["traceability", pct(overall.analyst_inspectability.mean_traceability)],
                      ["abstention proofs", pct(overall.analyst_inspectability.mean_abstention_proofs)],
                    ]}
                  />
                </section>

                <JudgePanel judge={overall.llm_judge} />

                {file && file.e2e.by_tier && <TierTable byTier={file.e2e.by_tier} />}
                {file && <Diagnosis lines={file.diagnosis} />}
              </>
            ) : (
              <EmptyState available={report.e2e_available} onRun={handleRun} running={running} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function SecondaryNav({
  note,
  running,
  judge,
  onToggleJudge,
  onRun,
}: {
  note?: string;
  running: boolean;
  judge: boolean;
  onToggleJudge: () => void;
  onRun: () => void;
}) {
  return (
    <div
      className="flex items-center justify-between gap-3 px-6 py-3"
      style={{ boxShadow: "inset 0 -1px 0 rgba(235,230,220,0.08)" }}
    >
      <div className="flex flex-col">
        <h1 className="m-0 text-[15px] font-semibold text-text">End-to-End Evaluation</h1>
        {note && <span className="font-mono text-[10px] text-text-muted">{note}</span>}
      </div>
      <div className="flex items-center gap-3">
        <label className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.06em] text-text-muted">
          <input
            type="checkbox"
            checked={judge}
            onChange={onToggleJudge}
            disabled={running}
            className="h-3 w-3 accent-[var(--color-primary)]"
          />
          LLM judge
        </label>
        <button
          type="button"
          onClick={onRun}
          disabled={running}
          className="rounded-md px-3.5 py-1.5 font-mono text-[11px] font-semibold uppercase tracking-[0.04em] transition-opacity hover:opacity-90 disabled:opacity-50"
          style={{ background: "var(--color-primary)", color: "var(--color-bg)" }}
        >
          {running ? "Running…" : "Run evaluation"}
        </button>
      </div>
    </div>
  );
}

function TierTable({ byTier }: { byTier: Record<string, E2EOverall> }) {
  const rows = Object.entries(byTier);
  if (!rows.length) return null;
  return (
    <section className="rounded-lg p-4" style={{ boxShadow: "rgba(235,230,220,0.08) 0 0 0 1px" }}>
      <h2 className="mb-3 font-mono text-[11px] uppercase tracking-[0.08em] text-text-soft">By tier</h2>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse font-mono text-[12px] tabular-nums">
          <thead>
            <tr className="text-left text-text-muted">
              <th className="py-1 pr-4 font-normal">Tier</th>
              <th className="py-1 pr-4 font-normal">X-source</th>
              <th className="py-1 pr-4 font-normal">Mapping</th>
              <th className="py-1 pr-4 font-normal">Provenance</th>
              <th className="py-1 font-normal">Inspectability</th>
            </tr>
          </thead>
          <tbody className="text-text-soft">
            {rows.map(([tier, agg]) => (
              <tr key={tier} style={{ boxShadow: "inset 0 1px 0 rgba(235,230,220,0.06)" }}>
                <td className="py-1.5 pr-4 text-text">{tier}</td>
                <td className="py-1.5 pr-4">{pct(agg.cross_source_accuracy.exact_match.rate)}</td>
                <td className="py-1.5 pr-4">{pct(agg.mapping_recall.micro_recall)}</td>
                <td className="py-1.5 pr-4">{pct(agg.provenance_correctness.fully_provenanced.rate)}</td>
                <td className="py-1.5">{pct(agg.analyst_inspectability.mean_inspectability)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Diagnosis({ lines }: { lines: string[] }) {
  if (!lines?.length) return null;
  return (
    <section className="rounded-lg p-4" style={{ boxShadow: "rgba(235,230,220,0.08) 0 0 0 1px" }}>
      <h2 className="mb-2 font-mono text-[11px] uppercase tracking-[0.08em] text-text-soft">Diagnosis</h2>
      <ul className="m-0 flex list-disc flex-col gap-1.5 pl-5 text-[13px] leading-relaxed text-text-soft">
        {lines.map((line, i) => (
          <li key={i}>{line}</li>
        ))}
      </ul>
    </section>
  );
}

function RunLog({ lines }: { lines: string[] }) {
  return (
    <section
      className="max-h-48 overflow-y-auto rounded-lg p-3 font-mono text-[11px] leading-relaxed"
      style={{ background: "var(--color-console)", color: "var(--color-text-muted)" }}
    >
      {lines.map((line, i) => (
        <div key={i} className="whitespace-pre-wrap">{line}</div>
      ))}
    </section>
  );
}

function EmptyState({
  available,
  onRun,
  running,
}: {
  available: boolean;
  onRun: () => void;
  running: boolean;
}) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-lg py-16 text-center" style={{ boxShadow: "rgba(235,230,220,0.08) 0 0 0 1px" }}>
      <p className="max-w-md font-sans text-[13px] leading-relaxed text-text-muted">
        {available
          ? "The committed report was generated hermetically (no live scoring). Run the end-to-end evaluation with the graph stack up to populate the metrics."
          : "No end-to-end report has been generated yet. Run the evaluation to score the pipeline against the golden catalogue."}
      </p>
      <button
        type="button"
        onClick={onRun}
        disabled={running}
        className="rounded-md px-4 py-2 font-mono text-[12px] font-semibold transition-opacity hover:opacity-90 disabled:opacity-50"
        style={{ background: "var(--color-primary)", color: "var(--color-bg)" }}
      >
        {running ? "Running…" : "Run evaluation"}
      </button>
    </div>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full items-center justify-center">
      <p className="font-mono text-[12px] uppercase tracking-[0.08em] text-text-muted">{children}</p>
    </div>
  );
}

function ErrorCard({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 py-16 text-center">
      <p className="font-mono text-[11px] uppercase tracking-[0.08em] text-secondary">Failed to load evaluation</p>
      <p className="font-sans text-[13px] leading-relaxed text-text-muted">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="rounded-md px-4 py-2 font-sans text-[13px] font-medium transition-opacity hover:opacity-90"
        style={{ background: "var(--color-primary)", color: "var(--color-bg)" }}
      >
        Retry
      </button>
    </div>
  );
}
