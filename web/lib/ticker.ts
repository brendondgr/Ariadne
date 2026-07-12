import type { Accent, StampedQueryEvent } from "./types";

/** One narrated line in the live activity ticker. */
export interface TickerLine {
  /** Stable key for AnimatePresence (event index). */
  key: string;
  /** Elapsed time label at arrival, e.g. "0.4s" ("" when unstamped). */
  time: string;
  /** Compact one-line narration of what just happened. */
  text: string;
  accent: Accent;
  /** Terminal lines (done/error) end the stream. */
  terminal?: boolean;
}

function fmtTime(ms: number | undefined): string {
  if (ms === undefined) return "";
  return `${(ms / 1000).toFixed(1)}s`;
}

/**
 * Project one captured SSE event into a ticker line, or null for events that
 * add no narration beyond what a neighbouring event already says.
 * Pure — unit-tested in node; the component only renders the result.
 */
export function describeEvent(event: StampedQueryEvent, index: number): TickerLine | null {
  const key = `evt-${index}`;
  const time = fmtTime(event.receivedMs);
  switch (event.type) {
    case "status": {
      const phase = event.data.phase;
      const label =
        phase === "probing"
          ? "probing graph backends…"
          : phase === "classifying"
            ? "classifying analyst intent…"
            : phase === "planning"
              ? "planning and routing the question…"
              : phase === "querying"
                ? `querying ${event.data.count ?? ""} source specialist(s)…`.replace("  ", " ")
                : phase === "answering"
                  ? "composing and verifying the answer…"
                  : null;
      return label ? { key, time, text: label, accent: "sage" } : null;
    }
    case "probe": {
      const parts = event.data.live_sources.map((s) =>
        s.live ? `${s.dataset} live (${s.node_count} nodes)` : `${s.dataset} DOWN`,
      );
      return { key, time, text: `probe: ${parts.join(" · ")}`, accent: "teal" };
    }
    case "plan": {
      const n = event.data.plan.sub_questions.length;
      const routed = event.data.target_sources.join(" + ");
      const joins = event.data.plan.joins.length
        ? ` · join on ${event.data.plan.joins.map((j) => j.key).join(", ")}`
        : "";
      return {
        key,
        time,
        text: `plan: ${n} sub-question(s) → ${routed || "(none)"}${joins}`,
        accent: "teal",
      };
    }
    case "specialist-start": {
      if (event.data.skipped) {
        return {
          key,
          time,
          text: `${event.data.sub_question} [${event.data.source}] skipped — ${event.data.skipped}`,
          accent: "amber",
        };
      }
      const seeds = event.data.seed_count
        ? ` seeded with ${event.data.seed_count} id(s) from ${event.data.producer}`
        : "";
      return {
        key,
        time,
        text: `${event.data.sub_question} [${event.data.source}] querying…${seeds}`,
        accent: "teal",
      };
    }
    case "specialist": {
      const r = event.data.result;
      const source = r.task.source;
      const n = r.records.length;
      if (r.ok && n === 0 && !r.query) {
        return { key, time, text: `${source}: no query executed (honest empty)`, accent: "amber" };
      }
      const state = r.ok ? "" : r.partial ? " (partial)" : " (FAILED)";
      return {
        key,
        time,
        text: `${source}: ${n} record(s) returned${state}`,
        accent: r.ok ? "teal" : "amber",
      };
    }
    case "skipped":
      return {
        key,
        time,
        text: `${event.data.sub_question} [${event.data.source}] skipped — ${event.data.reason}`,
        accent: "amber",
      };
    case "evidence": {
      const cross = event.data.evidence.cross_source_join_values.length;
      return {
        key,
        time,
        text: `evidence bundled · ${cross} cross-source correlation(s)`,
        accent: "teal",
      };
    }
    case "answer": {
      const verification = event.data.synthesis?.verification;
      const conflicts = verification?.conflict_count ?? 0;
      const text = verification
        ? `answer verified · ${verification.supported_count}/${verification.verdicts.length} claim(s) supported` +
          (conflicts ? ` · reconcile: ${conflicts} source conflict(s)` : "")
        : "answer composed";
      return { key, time, text, accent: conflicts ? "amber" : "teal" };
    }
    case "done": {
      const status = event.data.status;
      return {
        key,
        time,
        text: `done · ${status} (exit ${event.data.exit_code})`,
        accent: status === "answered" ? "teal" : "amber",
        terminal: true,
      };
    }
    case "error":
      return { key, time, text: `error · ${event.data.message}`, accent: "amber", terminal: true };
    default:
      return null;
  }
}

/** Project a whole captured event log into ticker lines (nulls dropped). */
export function tickerLines(events: StampedQueryEvent[]): TickerLine[] {
  return events
    .map((event, i) => describeEvent(event, i))
    .filter((line): line is TickerLine => line !== null);
}

/** The latest phase message from the captured status events, or null. */
export function currentPhaseMessage(events: StampedQueryEvent[]): string | null {
  for (let i = events.length - 1; i >= 0; i--) {
    const event = events[i];
    if (event.type === "status") {
      return event.data.message ?? event.data.phase ?? null;
    }
  }
  return null;
}
