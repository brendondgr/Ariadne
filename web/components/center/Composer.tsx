"use client";

import { useState } from "react";
import { SHADOW } from "@/lib/ui";
import { SendArrow } from "@/components/ui/icons";

type Mode = "plan" | "query";
type Drafter = "deterministic" | "llm";

/** The docked composer: question input, Plan/Full-answer mode toggle, the
 *  deterministic/LLM drafter toggle, and Send. (Submit is wired to the run
 *  machine in a later phase.) */
export function Composer() {
  const [mode, setMode] = useState<Mode>("query");
  const [drafter, setDrafter] = useState<Drafter>("deterministic");

  return (
    <div className="flex-[0_0_auto] px-[22px] pb-[18px] pt-3">
      <div
        className="rounded-[13px] bg-surface px-3.5 py-3"
        style={{ boxShadow: SHADOW.composer }}
      >
        <textarea
          rows={1}
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
            className="flex items-center gap-[7px] rounded-lg border-0 bg-primary px-[15px] py-2 font-mono text-xs font-semibold text-bg transition-colors hover:bg-[#5bb0a7]"
          >
            Send
            <SendArrow />
          </button>
        </div>
      </div>
    </div>
  );
}
