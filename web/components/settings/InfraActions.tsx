"use client";

import { useEffect, useRef, useState } from "react";
import type { AdminAction, AdminActionBody } from "@/lib/types";
import { streamAdmin } from "@/lib/api";
import { CONSOLE_BG, SHADOW } from "@/lib/ui";

type Dataset = "attack" | "capec" | "all";
type Graph = "neo4j" | "gremlin" | "all";

const NEEDS_DATASET: AdminAction[] = ["graph-load", "graph-verify", "data-build"];
const NEEDS_GRAPH: AdminAction[] = ["graph-load", "graph-stop"];

const BUTTONS: { group: string; actions: { action: AdminAction; label: string; danger?: boolean }[] }[] = [
  {
    group: "Docker",
    actions: [
      { action: "docker-status", label: "Status" },
      { action: "docker-start", label: "Start" },
      { action: "docker-stop", label: "Stop", danger: true },
    ],
  },
  {
    group: "Graph",
    actions: [
      { action: "graph-health", label: "Health" },
      { action: "graph-load", label: "Load" },
      { action: "graph-verify", label: "Verify" },
      { action: "graph-stop", label: "Stop", danger: true },
    ],
  },
  {
    group: "Data",
    actions: [
      { action: "data-download", label: "Download" },
      { action: "data-build", label: "Build" },
    ],
  },
  {
    group: "Pipeline",
    actions: [{ action: "yolo-all", label: "yolo-all (full pipeline)", danger: true }],
  },
];

/** Admin console: run the infra/data/graph actions main.py exposes and stream
 *  their logs. These are host-dependent operations (Docker, network, graph
 *  loads); output and success are shown live. */
export function InfraActions() {
  const [logs, setLogs] = useState<string[]>([]);
  const [running, setRunning] = useState<AdminAction | null>(null);
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [dataset, setDataset] = useState<Dataset>("attack");
  const [graph, setGraph] = useState<Graph>("all");
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [logs]);

  const run = async (action: AdminAction) => {
    if (running) return;
    setRunning(action);
    setResult(null);
    setLogs([]);
    const body: AdminActionBody = {
      action,
      ...(NEEDS_DATASET.includes(action) ? { dataset } : {}),
      ...(NEEDS_GRAPH.includes(action) ? { graph } : {}),
    };
    try {
      await streamAdmin(body, (event) => {
        if (event.type === "log") setLogs((l) => [...l, event.data.line]);
        else if (event.type === "status")
          setLogs((l) => [...l, `· ${event.data.message ?? event.data.action}`]);
        else if (event.type === "done") setResult({ ok: event.data.ok, message: event.data.message });
      });
    } catch (err) {
      setResult({ ok: false, message: err instanceof Error ? err.message : String(err) });
    } finally {
      setRunning(null);
    }
  };

  return (
    <fieldset className="m-0 rounded-lg border-0 p-3.5" style={{ boxShadow: SHADOW.border }}>
      <legend className="px-1 font-mono text-[11px] uppercase tracking-[0.08em] text-text-soft">
        Infrastructure &amp; data
      </legend>

      <p className="mb-2.5 mt-1 text-[11.5px] leading-snug text-text-muted">
        Host operations from <span className="font-mono text-text-soft">main.py</span> — Docker, dataset
        downloads/builds, graph load/verify/stop, and the full <span className="font-mono text-text-soft">--yolo-all</span>
        pipeline. Output streams below; success depends on the host.
      </p>

      <div className="mb-2.5 flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1.5 font-mono text-[11px] text-text-muted">
          dataset
          <select
            value={dataset}
            onChange={(e) => setDataset(e.target.value as Dataset)}
            className="rounded-md bg-bg px-1.5 py-1 text-[11px] text-text shadow-border outline-none"
          >
            <option value="attack">attack</option>
            <option value="capec">capec</option>
            <option value="all">all</option>
          </select>
        </label>
        <label className="flex items-center gap-1.5 font-mono text-[11px] text-text-muted">
          graph
          <select
            value={graph}
            onChange={(e) => setGraph(e.target.value as Graph)}
            className="rounded-md bg-bg px-1.5 py-1 text-[11px] text-text shadow-border outline-none"
          >
            <option value="neo4j">neo4j</option>
            <option value="gremlin">gremlin</option>
            <option value="all">all</option>
          </select>
        </label>
      </div>

      <div className="flex flex-col gap-2">
        {BUTTONS.map((row) => (
          <div key={row.group} className="flex items-center gap-2">
            <span className="w-[52px] shrink-0 font-mono text-[10px] uppercase tracking-[0.08em] text-text-faint">
              {row.group}
            </span>
            <div className="flex flex-wrap gap-1.5">
              {row.actions.map(({ action, label, danger }) => (
                <button
                  key={action}
                  type="button"
                  onClick={() => run(action)}
                  disabled={running !== null}
                  className="rounded-md border-0 bg-transparent px-2.5 py-1 font-mono text-[11px] text-text-soft shadow-border transition-colors hover:text-text disabled:opacity-45"
                  style={danger ? { color: "var(--color-secondary)" } : undefined}
                >
                  {running === action ? "…" : label}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {(logs.length > 0 || result) && (
        <div
          ref={logRef}
          className="mt-3 max-h-[180px] overflow-y-auto rounded-md p-2.5 font-mono text-[11px] leading-relaxed text-text-muted"
          style={{ background: CONSOLE_BG, boxShadow: SHADOW.border }}
        >
          {logs.map((line, i) => (
            <div key={i} className="whitespace-pre-wrap break-words">
              {line}
            </div>
          ))}
          {result && (
            <div className={`mt-1 ${result.ok ? "text-primary" : "text-secondary"}`}>
              {result.ok ? "✓ " : "✗ "}
              {result.message}
            </div>
          )}
        </div>
      )}
    </fieldset>
  );
}
