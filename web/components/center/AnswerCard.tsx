"use client";

import { Fragment, useMemo, useState } from "react";
import { motion } from "motion/react";
import type { AnswerParagraph, SynthesisView, WorkbenchRun } from "@/lib/types";
import { SHADOW, formatSeconds } from "@/lib/ui";
import { fadeSlideUp } from "@/lib/motion";
import {
  CheckIcon,
  CopyIcon,
  EvidenceIcon,
  ExportIcon,
  LinkIcon,
  LogsIcon,
  NetworkIcon,
  TableIcon,
  VerifiedIcon,
} from "@/components/ui/icons";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";
import { MiniStepper } from "./MiniStepper";
import { LiveTicker } from "./LiveTicker";
import { LiveAnswerStatus } from "./LiveAnswerStatus";
import { currentPhaseMessage } from "@/lib/ticker";
import { ProvenanceChip } from "./ProvenanceChip";
import { JoinChip } from "./JoinChip";
import { ClaimTableBody } from "./ClaimTable";
import { NetworkPlotBody, networkPlotMeta } from "./AnswerNetworkPlot";
import { buildEntityDetails } from "@/lib/synthesisGraph";
import { SectionTabs, type TabDef } from "./SectionTabs";

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

/** The Verified Answers tab body: the verification pill, verified claims with
 *  citations, honest abstentions with their proof (the executed query — or the
 *  named schema boundary when no query could express the question), and the
 *  audit trail of claims the verifier cut. */
function SynthesisBody({ synthesis }: { synthesis: SynthesisView }) {
  return (
    <div>
      <div className="mb-2.5">
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

/** The Evidence tab body: the per-source "Found …" prose plus the cross-source
 *  join candidates. */
function EvidenceBody({ run }: { run: WorkbenchRun }) {
  return (
    <div>
      <div className="text-sm leading-[1.62] text-text-soft">
        {run.answer.paragraphs.map((p, i) => (
          <Paragraph key={i} paragraph={p} />
        ))}
      </div>
      {run.answer.joinPairs.length > 0 && (
        <div className="mt-3">
          <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.08em] text-text-muted">
            Cross-source join candidates
          </div>
          <div className="flex flex-wrap gap-2">
            {run.answer.joinPairs.map((pair, i) => (
              <JoinChip key={i} pair={pair} />
            ))}
          </div>
        </div>
      )}
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

/** The structured assistant turn: status stepper, the natural-language answer (or
 *  a live "what it's doing" status while streaming), tabbed detail containers
 *  that appear as information is extracted, and a footer of actions + per-stage
 *  timings.
 *
 *  `live` is true only for the turn currently streaming; past turns render
 *  statically from their own baked status so they don't react to the global
 *  stream state. */
export function AnswerCard({ run, live = true }: { run: WorkbenchRun; live?: boolean }) {
  const { setActiveTab, openInspector, statusOf, replaying, error } = useWorkbench();
  const [copied, setCopied] = useState(false);
  const [exported, setExported] = useState(false);
  const cardReplaying = live && replaying;
  const answered = live ? statusOf("answer", "pass") === "pass" : run.status !== "running";
  const working = live && !answered;
  // Real names/descriptions for the network-plot nodes, projected once per turn
  // from the federated evidence the turn already carries. Must run before any
  // conditional return to keep hook order stable.
  const entityDetails = useMemo(
    () => buildEntityDetails(run.federated),
    [run.federated],
  );

  if (error && live && !replaying) return <AnswerError message={error} />;

  const openRawJson = () => {
    setActiveTab("raw");
    openInspector();
  };
  const copyEvidence = async () => {
    try {
      await navigator.clipboard?.writeText(JSON.stringify(run.federated, null, 2));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      // Clipboard blocked (insecure context / permissions) — leave state as-is.
    }
  };
  const exportEvidence = () => {
    const blob = new Blob([JSON.stringify(run.federated, null, 2)], {
      type: "application/json",
    });
    const href = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = href;
    a.download = `ariadne-evidence-${run.id}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(href);
    setExported(true);
    window.setTimeout(() => setExported(false), 1600);
  };

  // Tabs appear only as their data becomes available (progressive disclosure).
  const syn = run.answer.synthesis;
  const net = syn ? networkPlotMeta(syn, run.answer.joinPairs) : null;
  const tabs: TabDef[] = [];
  if (run.answer.paragraphs.length > 0) {
    tabs.push({
      id: "evidence",
      label: "Evidence",
      icon: <EvidenceIcon />,
      badge: run.answer.paragraphs.length,
      content: <EvidenceBody run={run} />,
    });
  }
  if (syn) {
    tabs.push({
      id: "verified",
      label: "Verified Answers",
      icon: <VerifiedIcon />,
      badge: syn.verification ? `${syn.verification.supported}/${syn.verification.total}` : undefined,
      content: <SynthesisBody synthesis={syn} />,
    });
  }
  if (syn && syn.claims.length > 0) {
    tabs.push({
      id: "claim",
      label: "Claim Table",
      icon: <TableIcon />,
      badge: syn.claims.length,
      content: <ClaimTableBody synthesis={syn} />,
    });
  }
  if (syn && net?.renderable) {
    tabs.push({
      id: "network",
      label: "Network Plot",
      icon: <NetworkIcon />,
      badge: net.nodeCount,
      content: (
        <NetworkPlotBody
          synthesis={syn}
          joinPairs={run.answer.joinPairs}
          entityDetails={entityDetails}
        />
      ),
    });
  }
  if (run.events.length > 0) {
    tabs.push({
      id: "logs",
      label: "Logs",
      icon: <LogsIcon />,
      content: <LiveTicker events={run.events} streaming={cardReplaying} alwaysOpen />,
    });
  }

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

      {/* The answer surface: live status while working, else the final answer. */}
      <div className="px-[18px] pb-4 pt-[18px]">
        {working ? (
          <LiveAnswerStatus events={run.events} createdAt={run.createdAt} />
        ) : syn ? (
          <>
            <div className="mb-[9px] font-mono text-[10px] uppercase tracking-[0.08em] text-text-muted">
              Final answer
            </div>
            <p className="m-0 text-sm leading-[1.62] text-text-soft">
              {syn.narrative || syn.headline}
            </p>
          </>
        ) : (
          <div className="text-sm leading-[1.62] text-text-soft">
            {run.answer.paragraphs.map((p, i) => (
              <Paragraph key={i} paragraph={p} />
            ))}
          </div>
        )}
      </div>

      {tabs.length > 0 && (
        <SectionTabs tabs={tabs} preferredId="network" streamingFallbackId="logs" />
      )}

      {/* Footer: actions on the left, per-stage timings (seconds) on the right. */}
      <div
        className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-[18px] py-[13px]"
        style={{ boxShadow: SHADOW.insetTop }}
      >
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
            aria-live="polite"
            className="inline-flex items-center gap-1.5 border-0 bg-transparent p-0 font-mono text-[11.5px] text-text-muted transition-colors hover:text-text"
            style={{ color: copied ? "var(--color-primary)" : undefined }}
          >
            {copied ? <CheckIcon /> : <CopyIcon />}
            {copied ? "Copied" : "Copy"}
          </button>
          <button
            type="button"
            onClick={exportEvidence}
            aria-live="polite"
            className="inline-flex items-center gap-1.5 border-0 bg-transparent p-0 font-mono text-[11.5px] text-text-muted transition-colors hover:text-text"
            style={{ color: exported ? "var(--color-primary)" : undefined }}
          >
            {exported ? <CheckIcon /> : <ExportIcon />}
            {exported ? "Exported" : "Export"}
          </button>
        </div>

        {run.answer.timings && (
          <div className="flex flex-wrap items-center justify-end gap-x-3 gap-y-1 font-mono text-[10.5px] text-text-muted">
            {run.answer.timings.map((t, i) => (
              <span key={i}>
                {t.label} <span className="text-text-soft">{formatSeconds(t.ms)}</span>
              </span>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}
