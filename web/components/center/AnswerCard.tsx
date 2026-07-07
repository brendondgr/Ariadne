"use client";

import { Fragment } from "react";
import { motion } from "motion/react";
import type { AnswerParagraph, SynthesisView, WorkbenchRun, StampedQueryEvent } from "@/lib/types";
import { SHADOW } from "@/lib/ui";
import { fadeSlideUp } from "@/lib/motion";
import { CopyIcon, ExportIcon, LinkIcon } from "@/components/ui/icons";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";
import { MiniStepper } from "./MiniStepper";
import { LiveTicker } from "./LiveTicker";
import { currentPhaseMessage } from "@/lib/ticker";
import { ProvenanceChip } from "./ProvenanceChip";
import { JoinChip } from "./JoinChip";
import { ClaimTable } from "./ClaimTable";

function Paragraph({ paragraph }: { paragraph: AnswerParagraph }) {
  return (
    <p className="m-0 mb-3 last:mb-0">
      {paragraph.segments.map((seg, i) => {
        if (seg.kind === "text") return <Fragment key={i}>{seg.text}</Fragment>;
        if (seg.kind === "mono")
          return (
            <span key={i} className="font-mono text-[12px] text-[#c9c6bd]">
              {seg.text}
            </span>
          );
        return <ProvenanceChip key={i} refData={seg.ref} />;
      })}
    </p>
  );
}

/** Pill summarizing the verification pass: teal when everything the composer
 *  wrote survived, amber when the verifier had to cut claims or repair
 *  abstentions — honesty is the feature, so repairs are shown, not hidden. */
function VerificationPill({ synthesis }: { synthesis: SynthesisView }) {
  const v = synthesis.verification;
  if (!v) return null;
  const clean = v.ok && v.repairedAbstentions === 0;
  const tone = clean
    ? { color: "#4E9E96", ring: "rgba(78,158,150,0.5)", bg: "rgba(78,158,150,0.1)" }
    : { color: "#C9924A", ring: "rgba(201,146,74,0.5)", bg: "rgba(201,146,74,0.1)" };
  const parts = [
    `${v.supported}/${v.total} claim${v.total === 1 ? "" : "s"} verified`,
    `${Math.round(v.unsupportedRate * 100)}% unsupported`,
  ];
  if (v.repairedAbstentions) parts.push(`${v.repairedAbstentions} abstention repair(s)`);
  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-px font-mono text-[10.5px]"
      style={{ color: tone.color, background: tone.bg, boxShadow: `${tone.ring} 0 0 0 1px` }}
    >
      {parts.join(" · ")}
    </span>
  );
}

/** The Step 6/7 trust surface: verified claims with citations, honest
 *  abstentions with their proof (the executed query — or the named schema
 *  boundary when no query could express the question), and the audit trail of
 *  claims the verifier cut. */
function SynthesisBlock({ synthesis }: { synthesis: SynthesisView }) {
  return (
    <div className="px-[18px] py-[13px]" style={{ boxShadow: SHADOW.insetBottom }}>
      <div className="mb-[9px] flex flex-wrap items-center gap-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-text-muted">
          Verified answer
        </span>
        <VerificationPill synthesis={synthesis} />
      </div>

      {synthesis.claims.map((claim, i) => (
        <p key={`claim-${i}`} className="m-0 mb-2 text-[13px] leading-[1.6] text-text-soft">
          <span className="mr-1.5 font-mono text-[10px] uppercase tracking-[0.06em] text-text-muted">
            {claim.kind === "correlation" ? "corr" : "fact"}
          </span>
          {claim.text}{" "}
          {claim.chips.map((chip, j) => (
            <span key={j} className="mr-1">
              <ProvenanceChip refData={chip} />
            </span>
          ))}
        </p>
      ))}

      {synthesis.abstentions.map((abst, i) => (
        <div
          key={`abst-${i}`}
          className="mb-2 rounded-[8px] px-3 py-2.5"
          style={{ boxShadow: SHADOW.hairline, background: "rgba(235,230,220,0.03)" }}
        >
          <p className="m-0 text-[13px] leading-[1.55] text-text-soft">{abst.statement}</p>
          <div className="mt-1.5 font-mono text-[11px] leading-[1.5] text-[#c9c6bd]">
            {abst.query ? (
              <>
                <span className="uppercase tracking-[0.06em] text-text-muted">
                  proof · executed query
                </span>
                <div className="whitespace-pre-wrap break-all">{abst.query}</div>
              </>
            ) : (
              <span className="uppercase tracking-[0.06em] text-text-muted">
                proof · no query executed — the {abst.source} source doesn&apos;t model this
              </span>
            )}
          </div>
        </div>
      ))}

      {synthesis.flagged.map((flag, i) => (
        <div
          key={`flag-${i}`}
          className="mb-2 rounded-[8px] px-3 py-2.5"
          style={{
            boxShadow: "rgba(201,146,74,0.45) 0 0 0 1px",
            background: "rgba(201,146,74,0.06)",
          }}
        >
          <div className="mb-0.5 font-mono text-[10px] uppercase tracking-[0.06em] text-secondary">
            Cut by verifier
          </div>
          <p className="m-0 text-[13px] leading-[1.55] text-text-soft line-through decoration-[rgba(201,146,74,0.6)]">
            {flag.text}
          </p>
          {flag.reasons.length > 0 && (
            <p className="m-0 mt-1 font-mono text-[11px] text-text-muted">
              {flag.reasons.join("; ")}
            </p>
          )}
        </div>
      ))}

      {synthesis.notes.map((note, i) => (
        <p key={`note-${i}`} className="m-0 mb-1 font-mono text-[11px] text-text-muted">
          ! {note}
        </p>
      ))}

      {synthesis.fallbackReason && (
        <p className="m-0 font-mono text-[11px] text-text-muted">
          composer: {synthesis.composer} — {synthesis.fallbackReason}
        </p>
      )}
    </div>
  );
}

/** Skeleton shown while the run streams, before the answer stage completes. */
function AnswerSkeleton({ events = [] }: { events?: StampedQueryEvent[] }) {
  return (
    <div
      className="max-w-[92%] rounded-[4px_13px_13px_13px] bg-surface px-[18px] py-5"
      style={{ boxShadow: SHADOW.border }}
    >
      <div className="mb-4 font-mono text-[11px] uppercase tracking-[0.08em] text-text-muted">
        Probing sources · running specialists…
      </div>
      <div className="flex flex-col gap-2.5">
        <div className="animate-skel h-3 w-[92%] rounded bg-[rgba(235,230,220,0.08)]" />
        <div className="animate-skel h-3 w-[78%] rounded bg-[rgba(235,230,220,0.08)]" />
        <div className="animate-skel h-3 w-[85%] rounded bg-[rgba(235,230,220,0.08)]" />
      </div>
      <div className="mt-4">
        <LiveTicker events={events} streaming />
      </div>
    </div>
  );
}

/** Shown when the stream fails (network error, backend exception). */
function AnswerError({ message }: { message: string }) {
  return (
    <div
      className="max-w-[92%] rounded-[4px_13px_13px_13px] bg-surface px-[18px] py-5"
      style={{ boxShadow: "rgba(201,146,74,0.6) 0 0 0 1px" }}
    >
      <div className="mb-2 font-mono text-[11px] uppercase tracking-[0.08em] text-secondary">
        Query failed
      </div>
      <p className="m-0 text-sm leading-[1.6] text-text-soft">{message}</p>
    </div>
  );
}

/** The structured assistant turn: status stepper, grounded prose with inline
 *  provenance chips, and a footer of join candidates + evidence actions.
 *
 *  `live` is true only for the turn currently streaming; past turns render
 *  statically from their own baked status so they don't react to the global
 *  stream state. */
export function AnswerCard({ run, live = true }: { run: WorkbenchRun; live?: boolean }) {
  const { setActiveTab, openInspector, statusOf, replaying, error } = useWorkbench();
  const cardReplaying = live && replaying;
  const answered = live ? statusOf("answer", "pass") === "pass" : run.status !== "running";

  if (cardReplaying && !answered) return <AnswerSkeleton events={run.events} />;
  if (error && live && !replaying) return <AnswerError message={error} />;

  const openRawJson = () => {
    setActiveTab("raw");
    openInspector();
  };
  const copyEvidence = () => {
    void navigator.clipboard?.writeText(JSON.stringify(run.federated, null, 2));
  };

  return (
    <motion.div
      variants={fadeSlideUp}
      initial={cardReplaying ? "hidden" : false}
      animate="show"
      className="max-w-[92%] overflow-hidden rounded-[4px_13px_13px_13px] bg-surface"
      style={{ boxShadow: SHADOW.answerCard }}
    >
      <MiniStepper
        steps={run.stepper}
        status={run.status}
        exitCode={run.exitCode}
        live={live}
        phase={currentPhaseMessage(run.events)}
        createdAt={run.createdAt}
      />

      <div className="px-[18px] pb-4 pt-[18px] text-sm leading-[1.62] text-text-soft">
        {run.answer.paragraphs.map((p, i) => (
          <Paragraph key={i} paragraph={p} />
        ))}
      </div>

      {run.answer.synthesis && <SynthesisBlock synthesis={run.answer.synthesis} />}

      {run.answer.synthesis && <ClaimTable synthesis={run.answer.synthesis} />}

      {run.events.length > 0 && (
        <div className="px-[18px] pb-1">
          <LiveTicker events={run.events} streaming={cardReplaying} />
        </div>
      )}

      {(run.answer.sequencingNotes.length > 0 || run.answer.timings) && (
        <div className="px-[18px] pb-2.5">
          {run.answer.sequencingNotes.map((note, i) => (
            <div key={i} className="mb-1 font-mono text-[10.5px] text-text-muted">
              ⇢ sequenced: {note}
            </div>
          ))}
          {run.answer.timings && (
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[10.5px] text-text-muted">
              {run.answer.timings.map((t, i) => (
                <span key={i}>
                  {t.label} <span className="text-text-soft">{Math.round(t.ms)}ms</span>
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="px-[18px] py-[13px]" style={{ boxShadow: SHADOW.insetBottom }}>
        <div className="mb-[9px] font-mono text-[10px] uppercase tracking-[0.08em] text-text-muted">
          Cross-source join candidates
        </div>
        <div className="mb-3.5 flex flex-wrap gap-2">
          {run.answer.joinPairs.map((pair, i) => (
            <JoinChip key={i} pair={pair} />
          ))}
        </div>
        <div className="flex items-center gap-3.5">
          <button
            type="button"
            onClick={openRawJson}
            className="inline-flex items-center gap-1.5 border-0 bg-transparent p-0 font-mono text-[11.5px] text-primary"
          >
            <LinkIcon />
            View full evidence JSON
          </button>
          <button
            type="button"
            onClick={copyEvidence}
            className="inline-flex items-center gap-1.5 border-0 bg-transparent p-0 font-mono text-[11.5px] text-text-muted transition-colors hover:text-text"
          >
            <CopyIcon />
            Copy
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-1.5 border-0 bg-transparent p-0 font-mono text-[11.5px] text-text-muted transition-colors hover:text-text"
          >
            <ExportIcon />
            Export
          </button>
        </div>
      </div>
    </motion.div>
  );
}
