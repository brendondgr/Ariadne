"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { GraphPayload } from "@/lib/types";
import type { FGNode, FGLink } from "@/lib/graph";
import { toForceGraphData } from "@/lib/graph";
import { getGraph } from "@/lib/api";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";
import { GraphSecondaryNav } from "./GraphSecondaryNav";
import { GraphSidebar } from "./GraphSidebar";
import { GraphDetailsSidebar } from "./GraphDetailsSidebar";
import { GraphCanvas } from "./GraphCanvas";
import type { SelectedElement } from "./ElementInspector";

/** Filter + selection state scoped to a specific dataset key. */
interface DatasetFilters {
  hiddenLabels: Set<string>;
  hiddenTypes: Set<string>;
  selected: SelectedElement;
}

const EMPTY_FILTERS: DatasetFilters = {
  hiddenLabels: new Set(),
  hiddenTypes: new Set(),
  selected: null,
};

/**
 * Top-level graph-explorer surface. Fills the <main> region:
 * - Secondary nav at top (dataset switcher + live counts)
 * - Flex row: GraphSidebar left + canvas region right
 */
export function GraphExplorer() {
  const { graphDataset } = useWorkbench();
  const [payload, setPayload] = useState<GraphPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  // All filter + selection state stored in a single map keyed by dataset.
  // Reading with a new key naturally returns undefined → falls back to EMPTY_FILTERS.
  // This avoids any useEffect-setState patterns the strict lint rules prohibit.
  const [filtersByDataset, setFiltersByDataset] = useState<
    Record<string, DatasetFilters>
  >({});

  const filters = filtersByDataset[graphDataset] ?? EMPTY_FILTERS;
  const { hiddenLabels, hiddenTypes, selected } = filters;

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

  /** Merge a partial update into the current dataset's filter state. */
  const updateFilters = useCallback(
    (patch: Partial<DatasetFilters>) => {
      setFiltersByDataset((prev) => ({
        ...prev,
        [graphDataset]: { ...(prev[graphDataset] ?? EMPTY_FILTERS), ...patch },
      }));
    },
    [graphDataset],
  );

  // Compute filtered force-graph data
  const fgData = useMemo(
    () =>
      payload
        ? toForceGraphData(payload, { hiddenLabels, hiddenTypes })
        : null,
    [payload, hiddenLabels, hiddenTypes],
  );

  // Filter callbacks (stable references)
  const handleToggleLabel = useCallback(
    (label: string, hidden: boolean) => {
      setFiltersByDataset((prev) => {
        const cur = prev[graphDataset] ?? EMPTY_FILTERS;
        const next = new Set(cur.hiddenLabels);
        if (hidden) next.add(label);
        else next.delete(label);
        return { ...prev, [graphDataset]: { ...cur, hiddenLabels: next } };
      });
    },
    [graphDataset],
  );

  const handleToggleType = useCallback(
    (type: string, hidden: boolean) => {
      setFiltersByDataset((prev) => {
        const cur = prev[graphDataset] ?? EMPTY_FILTERS;
        const next = new Set(cur.hiddenTypes);
        if (hidden) next.add(type);
        else next.delete(type);
        return { ...prev, [graphDataset]: { ...cur, hiddenTypes: next } };
      });
    },
    [graphDataset],
  );

  const handleResetFilters = useCallback(() => {
    updateFilters({ hiddenLabels: new Set(), hiddenTypes: new Set() });
  }, [updateFilters]);

  const handleSelectNode = useCallback(
    (node: FGNode) => {
      updateFilters({ selected: { kind: "node", node } });
    },
    [updateFilters],
  );

  const handleSelectLink = useCallback(
    (link: FGLink) => {
      updateFilters({
        selected: { kind: "link", link: link as FGLink & Record<string, unknown> },
      });
    },
    [updateFilters],
  );

  const handleCloseDetails = useCallback(() => {
    updateFilters({ selected: null });
  }, [updateFilters]);

  const datasetLabel = graphDataset === "attack" ? "ATT&CK" : "CAPEC";

  // Visible counts (after filtering)
  const visibleCounts = fgData
    ? { nodes: fgData.nodes.length, links: fgData.links.length }
    : null;

  const selectedId =
    selected?.kind === "node"
      ? selected.node.id
      : selected?.kind === "link"
        ? selected.link.id
        : null;

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      {/* Secondary nav — dataset switcher */}
      <GraphSecondaryNav counts={payload?.counts ?? null} />

      {/* Body row: sidebar + canvas */}
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <GraphSidebar
          payload={payload}
          hiddenLabels={hiddenLabels}
          hiddenTypes={hiddenTypes}
          onToggleLabel={handleToggleLabel}
          onToggleType={handleToggleType}
          onResetFilters={handleResetFilters}
        />

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
            {/* Visible count badge */}
            {visibleCounts && !loading && !error && fgData && fgData.nodes.length > 0 && (
              <div
                className="absolute right-3 top-3 z-10 rounded-md px-2 py-1 font-mono text-[10px] tabular-nums"
                style={{
                  background: "rgba(21,25,26,0.85)",
                  color: "var(--color-text-muted)",
                  boxShadow: "rgba(235,230,220,0.08) 0 0 0 1px",
                  fontFeatureSettings: '"tnum"',
                }}
              >
                {visibleCounts.nodes.toLocaleString()} nodes · {visibleCounts.links.toLocaleString()} edges
              </div>
            )}

            {loading && (
              <CanvasLoading label={datasetLabel} />
            )}

            {!loading && error && (
              <CanvasError message={error} onRetry={handleRetry} />
            )}

            {!loading && !error && payload && payload.counts.nodes === 0 && (
              <CanvasEmpty />
            )}

            {!loading && !error && fgData && fgData.nodes.length === 0 && payload && payload.counts.nodes > 0 && (
              <CanvasAllFiltered />
            )}

            {!loading && !error && fgData && fgData.nodes.length > 0 && (
              <GraphCanvas
                data={fgData}
                onSelectNode={handleSelectNode}
                onSelectLink={handleSelectLink}
                selectedId={selectedId}
              />
            )}
          </div>
        </div>

        {/* Right sidebar — appears only when a node/edge is selected */}
        <GraphDetailsSidebar selected={selected} onClose={handleCloseDetails} />
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

function CanvasAllFiltered() {
  return (
    <p className="font-mono text-[12px] uppercase tracking-[0.08em]" style={{ color: "var(--color-text-muted)" }}>
      All nodes filtered. Adjust filters to show the graph.
    </p>
  );
}
