/**
 * Serialize a conversation thread into shareable Markdown.
 *
 * Used by the thread header's "Export chat" action so an analyst can copy the
 * whole conversation (every question + its assistant reply, with how each was
 * answered) and paste it elsewhere — e.g. to share it back in chat.
 */

import type { WorkbenchRun } from "./types";

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
