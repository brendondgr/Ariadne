/**
 * Serialize a conversation thread into shareable Markdown.
 *
 * Used by the thread header's "Export" menu:
 *  - `buildChatExport` (Chat Only) — every question + its assistant reply, with
 *    how each turn was answered; the shareable summary.
 *  - `buildFullHistoryExport` (Full History) — the same, plus a step-by-step
 *    "Pipeline" trace of what each turn did in what order (routing decision,
 *    planner stages, each specialist query and its record count, sequencing,
 *    validation verdict, and per-stage timings).
 *
 * Both are pure serializers over the `WorkbenchRun[]` the UI already holds, so
 * an analyst can copy a conversation and paste it elsewhere — e.g. back in chat.
 */

import type { SpecialistLane, WorkbenchRun } from "./types";

function routeLabel(run: WorkbenchRun): string {
  if (run.reply?.route === "quick") return "answered from memory";
  if (run.reply?.route === "graph") return "queried the graphs";
  return "answered";
}

function assistantText(run: WorkbenchRun): string {
  const text = run.reply?.text?.trim();
  if (text) return text;
  // Fallback for a turn with no conversational reply (mid-stream / legacy).
  const headline = run.answer.paragraphs
    .flatMap((p) => p.segments)
    .filter((s) => s.kind === "text")
    .map((s) => ("text" in s ? s.text : ""))
    .join("")
    .trim();
  return headline || "_(no reply captured)_";
}

/** Build a Markdown transcript of the whole thread. */
export function buildChatExport(title: string, runs: WorkbenchRun[]): string {
  const heading = `# ${title || "Conversation"}`;
  if (runs.length === 0) {
    return `${heading}\n\n_(no messages yet)_\n`;
  }

  const blocks = runs.map((run, i) => {
    const question = run.question.trim() || "_(empty question)_";
    return [
      `## ${i + 1}. You`,
      "",
      question,
      "",
      `**Assistant** _(${routeLabel(run)})_:`,
      "",
      assistantText(run),
    ].join("\n");
  });

  return `${heading}\n\n${blocks.join("\n\n---\n\n")}\n`;
}

/** Order specialist lanes by the order their results arrived (arrival.order),
 *  keeping array order for lanes with no arrival metadata (demo/legacy turns). */
function byArrival(a: SpecialistLane, b: SpecialistLane): number {
  const oa = a.arrival?.order ?? Number.POSITIVE_INFINITY;
  const ob = b.arrival?.order ?? Number.POSITIVE_INFINITY;
  return oa - ob;
}

/** The ordered "what the pipeline did" trace for one turn. */
function pipelineBlock(run: WorkbenchRun): string[] {
  const hasActivity = run.plannerStages.length > 0 || run.lanes.length > 0;
  // A memory-answered turn (or any turn with no graph activity) has no pipeline.
  if ((run.route ?? run.reply?.route) === "quick" || !hasActivity) {
    return ["**Pipeline:** answered from memory (no graph queried)."];
  }

  const lines: string[] = ["**Pipeline:**", ""];
  let step = 1;

  for (const stage of run.plannerStages) {
    const summary = stage.summary?.trim() ? ` — ${stage.summary.trim()}` : "";
    lines.push(`${step}. **${stage.title}** _(${stage.status})_${summary}`);
    step += 1;
  }

  for (const lane of [...run.lanes].sort(byArrival)) {
    lines.push(
      `${step}. **${lane.backend} · ${lane.title}** — ${lane.rows} record(s) in ${lane.ms} ms`,
    );
    step += 1;
    const query = lane.query?.trim();
    if (query) {
      lines.push("", `\`\`\`${lane.language}`, query, "```");
    }
    if (lane.error) {
      lines.push("", `_Error:_ ${lane.error}`);
    }
  }

  const sequencing = run.answer.sequencingNotes ?? [];
  if (sequencing.length > 0) {
    lines.push("", `_Sequencing:_ ${sequencing.join("; ")}`);
  }

  if (run.validation) {
    const reason = run.validation.reason?.trim()
      ? ` — ${run.validation.reason.trim()}`
      : "";
    lines.push("", `_Validation:_ ${run.validation.verdict}${reason}`);
  }

  const timings = run.answer.timings;
  if (timings && timings.length > 0) {
    lines.push(
      "",
      `_Timings:_ ${timings.map((t) => `${t.label} ${t.ms}ms`).join(", ")}`,
    );
  }

  return lines;
}

/** Build a Markdown transcript of the whole thread WITH the step-by-step
 *  pipeline trace for each turn (the "Full History" export). */
export function buildFullHistoryExport(title: string, runs: WorkbenchRun[]): string {
  const heading = `# ${title || "Conversation"}`;
  if (runs.length === 0) {
    return `${heading}\n\n_(no messages yet)_\n`;
  }

  const blocks = runs.map((run, i) => {
    const question = run.question.trim() || "_(empty question)_";
    return [
      `## ${i + 1}. You`,
      "",
      question,
      "",
      ...pipelineBlock(run),
      "",
      `**Assistant** _(${routeLabel(run)})_:`,
      "",
      assistantText(run),
    ].join("\n");
  });

  return `${heading}\n\n${blocks.join("\n\n---\n\n")}\n`;
}
