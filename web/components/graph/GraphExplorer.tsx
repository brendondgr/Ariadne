"use client";

import { useEffect, useRef, useState } from "react";
import type { GraphPayload } from "@/lib/types";
import { getGraph } from "@/lib/api";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";
import { GraphSecondaryNav } from "./GraphSecondaryNav";
import { GraphSidebar } from "./GraphSidebar";

/**
 * Top-level graph-explorer surface. Fills the <main> region:
 * - Secondary nav at top (dataset switcher + live counts)
 * - Flex row: GraphSidebar left + canvas region right
 * Canvas is a styled placeholder — the real canvas renders in the next step.
 */
export function GraphExplorer() {
  const { graphDataset } = useWorkbench();
  const [payload, setPayload] = useState<GraphPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  // Track the abort controller so cleanup/dataset-change aborts in-flight fetch
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    // Abort any prior fetch
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    async function fetchGraph() {
      setLoading(true);
      setError(null);
      setPayload(null);
      try {
        const data = await getGraph(graphDataset, controller.signal);
        if (!controller.signal.aborted) {
          setPayload(data);
          setLoading(false);
        }
      } catch (err: unknown) {
        if ((err as { name?: string }).name === "AbortError") return;
        setError(err instanceof Error ? err.message : String(err));
        setLoading(false);
      }
    }

    void fetchGraph();

    return () => {
      controller.abort();
    };
  }, [graphDataset, retryKey]);

  const handleRetry = () => {
    setRetryKey((k) => k + 1);
  };

  const datasetLabel = graphDataset === "attack" ? "ATT&CK" : "CAPEC";

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      {/* Secondary nav — dataset switcher */}
      <GraphSecondaryNav counts={payload?.counts ?? null} />

      {/* Body row: sidebar + canvas */}
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <GraphSidebar payload={payload} />

        {/* Canvas region */}
        <div className="relative flex min-h-0 min-w-0 flex-1 p-4">
          <div
            className="relative flex min-h-0 flex-1 flex-col items-center justify-center overflow-hidden rounded-lg"
            style={{
              background: "var(--color-console, #1a2628)",
              boxShadow:
                "rgba(235,230,220,0.08) 0px 0px 0px 1px, rgba(0,0,0,0.25) 0px 2px 8px, rgba(0,0,0,0.15) 0px 8px 24px -8px",
            }}
          >
            {loading && (
              <CanvasLoading label={datasetLabel} />
            )}

            {!loading && error && (
              <CanvasError message={error} onRetry={handleRetry} />
            )}

            {!loading && !error && payload && payload.counts.nodes === 0 && (
              <CanvasEmpty />
            )}

            {!loading && !error && payload && payload.counts.nodes > 0 && (
              <CanvasPlaceholder payload={payload} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Canvas state panels                                                         */
/* -------------------------------------------------------------------------- */

function CanvasLoading({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center gap-3 text-center">
      {/* Subtle spinner ring */}
      <span
        className="block h-8 w-8 rounded-full border-2 border-transparent"
        style={{
          borderTopColor: "rgba(78,158,150,0.6)",
          borderRightColor: "rgba(78,158,150,0.2)",
          animation: "spin 1s linear infinite",
        }}
        aria-hidden="true"
      />
      <p className="font-mono text-[12px] uppercase tracking-[0.08em]" style={{ color: "var(--color-text-muted)" }}>
        Loading {label} graph…
      </p>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function CanvasError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex max-w-sm flex-col items-center gap-4 text-center">
      <p className="font-mono text-[11px] uppercase tracking-[0.08em]" style={{ color: "var(--color-secondary)" }}>
        Failed to load graph
      </p>
      <p className="font-sans text-[13px] leading-relaxed" style={{ color: "var(--color-text-muted)" }}>
        {message}
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="rounded-md px-4 py-2 font-sans text-[13px] font-medium transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        style={{
          background: "var(--color-primary)",
          color: "var(--color-bg)",
        }}
      >
        Retry
      </button>
    </div>
  );
}

function CanvasEmpty() {
  return (
    <p className="font-mono text-[12px] uppercase tracking-[0.08em]" style={{ color: "var(--color-text-muted)" }}>
      No nodes in this graph.
    </p>
  );
}

function CanvasPlaceholder({ payload }: { payload: GraphPayload }) {
  return (
    <div
      className="flex flex-col items-center gap-4 rounded-lg px-8 py-6 text-center"
      style={{
        background: "rgba(235,230,220,0.03)",
        boxShadow: "rgba(235,230,220,0.08) 0 0 0 1px",
      }}
    >
      {/* Backend · dataset badge */}
      <span
        className="inline-block rounded-full px-3 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em]"
        style={{
          background: "rgba(78,158,150,0.12)",
          color: "var(--color-primary)",
          boxShadow: "rgba(78,158,150,0.35) 0 0 0 1px",
        }}
      >
        {payload.backend} · {payload.dataset}
      </span>

      <p
        className="font-sans text-[15px] font-medium"
        style={{ color: "var(--color-text)", letterSpacing: "-0.02em" }}
      >
        {payload.counts.nodes.toLocaleString()} nodes · {payload.counts.relationships.toLocaleString()} edges
      </p>

      <p className="font-mono text-[11px] leading-relaxed" style={{ color: "var(--color-text-muted)", maxWidth: 320 }}>
        Graph data loaded — canvas renders in the next step.
      </p>
    </div>
  );
}
