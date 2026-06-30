"use client";

import { useState, useEffect, useRef } from "react";
import type { WorkbenchRun, QueryEventType, Accent } from "@/lib/types";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { Pill } from "@/components/ui/Pill";
import { ACCENT, SHADOW } from "@/lib/ui";

type Payload = "events" | "plan" | "probe" | "evidence" | "answer";

const PAYLOAD_LABELS: { key: Payload; label: string }[] = [
  { key: "events", label: "Events" },
  { key: "plan", label: "Plan" },
  { key: "probe", label: "Probe" },
  { key: "evidence", label: "Evidence" },
  { key: "answer", label: "Answer" },
];

/** Map an SSE event type to a display accent. */
function eventAccent(type: QueryEventType): Accent {
  if (type === "evidence") return "amber";
  if (type === "error" || type === "skipped") return "amber";
  if (type === "done" || type === "status") return "sage";
  return "teal";
}

/** Muted "nothing here" note. */
function EmptyNote({ children }: { children: string }) {
  return (
    <p className="font-mono text-[11px] text-text-muted italic">{children}</p>
  );
}

interface CopyButtonProps {
  getJson: () => string;
}

/** Small copy-to-clipboard button with a transient "Copied" confirmation. */
function CopyButton({ getJson }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Clean up timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current !== null) clearTimeout(timerRef.current);
    };
  }, []);

  const handleCopy = () => {
    if (!navigator.clipboard) return;
    navigator.clipboard.writeText(getJson()).then(() => {
      setCopied(true);
      if (timerRef.current !== null) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => setCopied(false), 1800);
    });
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="rounded-md border-0 bg-transparent px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.07em] text-text-muted shadow-border transition-colors hover:text-primary"
      style={{ boxShadow: SHADOW.hairline }}
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

/** Payload selector: a horizontal strip of small segmented buttons. */
function PayloadSelector({
  selected,
  onSelect,
}: {
  selected: Payload;
  onSelect: (p: Payload) => void;
}) {
  return (
    <div
      className="mb-3 flex gap-0.5 rounded-lg p-0.5"
      style={{ background: "rgba(235,230,220,0.04)", boxShadow: SHADOW.hairline }}
    >
      {PAYLOAD_LABELS.map(({ key, label }) => {
        const active = key === selected;
        return (
          <button
            key={key}
            type="button"
            onClick={() => onSelect(key)}
            aria-pressed={active}
            className="flex-1 rounded-[6px] border-0 px-2 py-[5px] font-mono text-[10.5px] tracking-[0.04em] transition-colors"
            style={
              active
                ? {
                    background: ACCENT.teal.tintBg,
                    color: ACCENT.teal.fg,
                    boxShadow: `${ACCENT.teal.ring} 0 0 0 1px`,
                  }
                : {
                    background: "transparent",
                    color: "var(--color-text-muted)",
                  }
            }
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

/** Single-payload block: a copy button row + CodeBlock. */
function JsonPayloadBlock({
  json,
  emptyMessage,
}: {
  json: string | null;
  emptyMessage: string;
}) {
  if (json === null) return <EmptyNote>{emptyMessage}</EmptyNote>;
  const getJson = () => json;
  return (
    <div>
      <div className="mb-1.5 flex justify-end">
        <CopyButton getJson={getJson} />
      </div>
      <CodeBlock code={json} lang="json" className="text-[10.5px] leading-[1.7]" />
    </div>
  );
}

/** The ordered SSE events view. */
function EventsView({ run }: { run: WorkbenchRun }) {
  const { events } = run;
  const getAllJson = () => JSON.stringify(events, null, 2);

  if (events.length === 0) {
    return <EmptyNote>No events captured (demo turn or not yet run).</EmptyNote>;
  }

  return (
    <div>
      <div className="mb-2.5 flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-text-muted">
          {events.length} event{events.length !== 1 ? "s" : ""} · pipeline order
        </span>
        <CopyButton getJson={getAllJson} />
      </div>
      <div className="flex flex-col gap-3">
        {events.map((evt, idx) => {
          const accent = eventAccent(evt.type);
          const dataJson = JSON.stringify(evt.data, null, 2);
          return (
            <div key={idx}>
              <div className="mb-1 flex items-center gap-2">
                <span className="font-mono text-[10px] text-text-faint">#{idx + 1}</span>
                <Pill accent={accent} variant="tint" className="px-2 py-0.5 text-[9.5px]">
                  {evt.type}
                </Pill>
              </div>
              <CodeBlock
                code={dataJson}
                lang="json"
                className="text-[10.5px] leading-[1.7]"
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** The Raw JSON tab — multi-payload inspector for the full pipeline. */
export function RawJsonTab({ run }: { run: WorkbenchRun }) {
  const [selected, setSelected] = useState<Payload>("events");

  return (
    <div>
      <PayloadSelector selected={selected} onSelect={setSelected} />

      {selected === "events" && <EventsView run={run} />}

      {selected === "plan" && (
        <>
          <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.08em] text-text-muted">
            Plan · plan.to_dict() (includes .trace iterations)
          </div>
          <JsonPayloadBlock
            json={run.rawPlan !== null ? JSON.stringify(run.rawPlan, null, 2) : null}
            emptyMessage="No plan captured for this turn."
          />
        </>
      )}

      {selected === "probe" && (
        <>
          <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.08em] text-text-muted">
            Probe · live_sources payload
          </div>
          <JsonPayloadBlock
            json={JSON.stringify(run.rawProbe, null, 2)}
            emptyMessage="No probe sources captured."
          />
        </>
      )}

      {selected === "evidence" && (
        <>
          <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.08em] text-text-muted">
            FederatedEvidence · evidence.to_dict()
          </div>
          <JsonPayloadBlock
            json={JSON.stringify(run.federated, null, 2)}
            emptyMessage="No federated evidence captured."
          />
        </>
      )}

      {selected === "answer" && (
        <>
          <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.08em] text-text-muted">
            Answer · composed answer payload
          </div>
          <JsonPayloadBlock
            json={run.rawAnswer !== null ? JSON.stringify(run.rawAnswer, null, 2) : null}
            emptyMessage="No answer captured for this turn."
          />
        </>
      )}
    </div>
  );
}
