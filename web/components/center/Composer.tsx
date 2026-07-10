"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { SHADOW } from "@/lib/ui";
import { SendArrow } from "@/components/ui/icons";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";

type Mode = "plan" | "query";
type Drafter = "deterministic" | "llm";

/** The docked composer: question input, Plan/Full-answer mode toggle, the
 *  deterministic/LLM drafter toggle, and Send — wired to the run machine's
 *  `submit`, which streams the live `/api/query` pipeline. */
export function Composer() {
  const { submit, replaying, registerComposerFill } = useWorkbench();
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<Mode>("query");
  // Default to the LLM drafter: it produces the natural-language final answer
  // (planner + specialists + synthesis narrator all use the LLM). Falls back to
  // the deterministic pipeline automatically when the endpoint is unreachable.
  const [drafter, setDrafter] = useState<Drafter>("llm");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Register the imperative fill handler a clicked reference (elsewhere in the
  // answer) invokes via `setComposerDraft`. It fills and focuses but never
  // auto-sends — the analyst reviews/edits (and can adjust mode/drafter) first.
  // The setState here runs from the click event, not during render/effect.
  useEffect(() => {
    registerComposerFill((text) => {
      setQuestion(text);
      const el = textareaRef.current;
      if (el) {
        el.focus();
        // Caret at the end so an edit appends naturally.
        const end = text.length;
        el.setSelectionRange(end, end);
        el.scrollIntoView({ block: "nearest" });
      }
    });
    return () => registerComposerFill(null);
  }, [registerComposerFill]);

  const canSend = question.trim().length > 0 && !replaying;

  const send = () => {
    if (!canSend) return;
    submit({ question: question.trim(), mode, drafter });
    // Clear the box immediately so the analyst can compose the next question
    // while this turn streams; refocus keeps the caret ready to type.
    setQuestion("");
    textareaRef.current?.focus();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className="flex-[0_0_auto] px-[22px] pb-[18px] pt-3">
      <div
        // Match the conversation column width (centered ~75% on large screens)
        // so the composer lines up under the messages.
        className="mx-auto w-full rounded-[13px] bg-surface px-3.5 py-3 lg:w-[75%]"
        style={{ boxShadow: SHADOW.composer }}
      >
        <textarea
          ref={textareaRef}
          rows={1}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={onKeyDown}
          aria-label="Ask an analyst question"
          placeholder="Ask an analyst question about the federated knowledge graph…"
          className="mb-3 w-full resize-none border-0 bg-transparent px-0.5 pt-0.5 text-sm text-text outline-none placeholder:text-text-faint"
        />
        <div className="flex items-center gap-2.5">
          {/* mode toggle */}
          <div
            className="flex overflow-hidden rounded-lg"
            style={{ boxShadow: SHADOW.border }}
            role="group"
            aria-label="Answer mode"
          >
            <button
              type="button"
              onClick={() => setMode("plan")}
              aria-pressed={mode === "plan"}
              title="--plan only"
              className={`border-0 px-[11px] py-1.5 font-mono text-[11px] transition-colors ${
                mode === "plan" ? "bg-[rgba(78,158,150,0.14)] text-primary" : "bg-transparent text-text-muted hover:text-text"
              }`}
            >
              Plan
            </button>
            <button
              type="button"
              onClick={() => setMode("query")}
              aria-pressed={mode === "query"}
              title="--query: runs specialists"
              className={`border-0 px-[11px] py-1.5 font-mono text-[11px] transition-colors ${
                mode === "query" ? "bg-[rgba(78,158,150,0.14)] text-primary" : "bg-transparent text-text-muted hover:text-text"
              }`}
              style={{ boxShadow: "rgba(235,230,220,0.1) -1px 0 0 0" }}
            >
              Full answer
            </button>
          </div>

          {/* drafter toggle */}
          <button
            type="button"
            onClick={() => setDrafter((d) => (d === "deterministic" ? "llm" : "deterministic"))}
            className="flex items-center gap-[7px] rounded-lg px-[11px] py-1.5 font-mono text-[11px] text-text-muted"
            style={{ boxShadow: SHADOW.border }}
            title="Toggle deterministic / LLM drafter (--plan-llm / --query-llm)"
          >
            <span
              aria-hidden
              className="h-[9px] w-[9px] rounded-full"
              style={{ background: drafter === "llm" ? "var(--color-primary)" : "var(--color-text-muted)" }}
            />
            Drafter: <span className="text-[#c9c6bd]">{drafter}</span>
          </button>

          <div className="flex-1" />

          <button
            type="button"
            onClick={send}
            disabled={!canSend}
            className="flex items-center gap-[7px] rounded-lg border-0 bg-primary px-[15px] py-2 font-mono text-xs font-semibold text-bg transition-colors hover:bg-[#5bb0a7] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {replaying ? "Running…" : "Send"}
            <SendArrow />
          </button>
        </div>
      </div>
    </div>
  );
}
