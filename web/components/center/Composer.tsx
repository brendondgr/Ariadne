"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { SHADOW } from "@/lib/ui";
import { SendArrow } from "@/components/ui/icons";
import { Dropdown } from "@/components/ui/Dropdown";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";

type Mode = "plan" | "query";
type Drafter = "deterministic" | "llm";

/** Named reasoning levels. The value is the server's `thinking_token_budget`.
 *
 *  Measured against `:9090` on one sufficiency call: `0` → 1.28 s and 31
 *  completion tokens, `256` → 9.74 s and 283, `512` → 9.13 s and 313. The cap
 *  binds — at 256 the model was clipped to 283 total tokens where it would
 *  otherwise spend 313 — and simply stops binding once it exceeds what the model
 *  wants for a given prompt, which is why 512 and 1024 look alike on an easy one.
 *
 *  `None` sends a real 0. That needs `thinking_budget_explicit` on the way down,
 *  because `DEFAULT_THINKING_BUDGET` is also 0 and the sender omits a falsy
 *  budget: without the flag a requested "None" would send nothing and get the
 *  model's own default, 11.27 s — the slowest option under the fastest label. */
const THINKING_LEVELS = [
  { value: 0, label: "None", hint: "no reasoning · ~1.3 s" },
  { value: 256, label: "Low", hint: "256 tokens" },
  { value: 512, label: "Medium", hint: "512 tokens" },
  { value: 1024, label: "High", hint: "1024 tokens" },
] as const;

/** The docked composer: question input, the three controls an analyst actually
 *  trades between, and Send.
 *
 *  It used to carry Plan/Full-answer, a Drafter toggle and Plain prose. Those
 *  named implementation seams rather than choices, and one of them was actively
 *  harmful: `drafter: "llm"` turned on the planner, the specialist AND the
 *  narrator together, so an analyst reaching for readable prose silently got
 *  query construction from a model — the path that scores 0.5000 against the
 *  template cascade's 0.9467.
 *
 *  Verify, Prose and Thinking name what is being traded: a second opinion on the
 *  evidence (~30 s), a model-written reply (~10 s), and how long either may
 *  reason. Both default off, which is the fast path; the deterministic claim
 *  verifier runs on every path regardless. */
export function Composer() {
  const { submit, replaying, registerComposerFill } = useWorkbench();
  const [question, setQuestion] = useState("");
  // Always a full answer. The Plan/Full-answer toggle is gone: a plan-only run
  // is a debugging view, and the inspector already renders the plan on every
  // turn, so it cost a control without adding a capability.
  const mode: Mode = "query";
  // Deterministic by default. This used to default to "llm" so the answer read
  // as natural language — but `drafter: "llm"` turns on the planner, the
  // SPECIALIST and the narrator together, so wanting readable prose silently
  // handed query construction to a model. That path scores 0.5000 where the
  // template cascade scores 0.9467 on the same unseen questions
  // (EXP-2026-09-007). Prose is now its own toggle below, which reaches only
  // the narrator seam — the one measured not to change a fact.
  const [drafter] = useState<Drafter>("deterministic");
  // Both off by default: that is the fast path. `verify` is the LLM sufficiency
  // check (~28.6 s) and `narrate` lets the answer agent write the reply
  // (~10.7 s); with both off a turn is the pipeline plus the router, and the
  // deterministic claim verifier still runs either way.
  const [verify, setVerify] = useState(false);
  const [narrate, setNarrate] = useState(false);
  const [thinking, setThinking] = useState<number>(512);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Grow the textarea with its content, capped at 6 lines — beyond that it
  // scrolls internally rather than pushing the toolbar down. Runs whenever the
  // question changes (typing, imperative fill, and clear-on-send all covered).
  const MAX_LINES = 6;
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const style = getComputedStyle(el);
    const lineHeight = parseFloat(style.lineHeight) || 20;
    const pad = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
    const maxHeight = lineHeight * MAX_LINES + pad;
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`;
    el.style.overflowY = el.scrollHeight > maxHeight ? "auto" : "hidden";
  }, [question]);

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
    submit({
      question: question.trim(),
      mode,
      drafter,
      verify,
      narrate,
      // `?? null` rather than `||`: a budget of 0 is a real choice ("None"),
      // and `||` would collapse it to null, which means "leave the server's
      // value alone" -- the opposite instruction.
      thinking_budget: verify || narrate ? thinking : null,
    });
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
          className="composer-input mb-3 w-full resize-none border-0 bg-transparent px-0.5 pt-0.5 text-sm text-text outline-none placeholder:text-text-faint"
        />
        <div className="flex items-center gap-2.5">
          {/* verify — the LLM sufficiency check */}
          <button
            type="button"
            onClick={() => setVerify((v) => !v)}
            className="flex items-center gap-[7px] rounded-lg px-[11px] py-1.5 font-mono text-[11px] text-text-muted"
            style={{ boxShadow: SHADOW.border }}
            title="Ask a model whether the gathered evidence is sufficient, and retry retrieval if not. A second opinion, not the guarantee — every claim is checked against its cited evidence either way. Adds roughly 30 seconds."
          >
            <span
              aria-hidden
              className="h-[9px] w-[9px] rounded-full"
              style={{ background: verify ? "var(--color-primary)" : "var(--color-text-muted)" }}
            />
            Verify: <span className="text-[#c9c6bd]">{verify ? "on" : "off"}</span>
          </button>

          {/* readable prose — the answer agent writes the reply */}
          <button
            type="button"
            onClick={() => setNarrate((n) => !n)}
            className="flex items-center gap-[7px] rounded-lg px-[11px] py-1.5 font-mono text-[11px] text-text-muted"
            style={{ boxShadow: SHADOW.border }}
            title="Have a model write the reply over claims already composed and verified, instead of showing the composed narrative. It cannot add, remove or alter a claim. Adds roughly 10 seconds."
          >
            <span
              aria-hidden
              className="h-[9px] w-[9px] rounded-full"
              style={{ background: narrate ? "var(--color-primary)" : "var(--color-text-muted)" }}
            />
            Prose: <span className="text-[#c9c6bd]">{narrate ? "on" : "off"}</span>
          </button>

          {/* thinking level — inert while no model seam is on */}
          <Dropdown
            label="Thinking:"
            value={thinking}
            options={THINKING_LEVELS}
            onChange={setThinking}
            disabled={!verify && !narrate}
            title="How long the model steps may reason. None is a real 7x saving; Low, Medium and High are close together on this model. Inert while Verify and Prose are both off."
          />

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
