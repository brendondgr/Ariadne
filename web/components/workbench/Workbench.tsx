"use client";

import { AppShell } from "@/components/shell/AppShell";
import { HeaderBar } from "@/components/header/HeaderBar";
import { ConversationsPanel } from "@/components/left/ConversationsPanel";
import { ChatThread } from "@/components/center/ChatThread";
import { InspectorPanel } from "@/components/inspector/InspectorPanel";
import { InspectorDrawer } from "@/components/inspector/InspectorDrawer";
import { SettingsPanel } from "@/components/settings/SettingsPanel";
import { GraphExplorer } from "@/components/graph/GraphExplorer";
import { EvaluationDashboard } from "@/components/evaluation/EvaluationDashboard";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";
import type { ConversationSummary } from "@/lib/types";

/** Relative time label for a turn (computed at render; not auto-updating). */
function relTime(ts: number): string {
  if (!ts) return "demo";
  const s = Math.max(0, Math.round((Date.now() - ts) / 1000));
  if (s < 5) return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  return `${Math.round(m / 60)}h ago`;
}

/**
 * Client orchestrator: reads the multi-turn conversation from the run machine
 * and feeds it to the three regions as props. The left rail, center thread, and
 * inspector all derive from `runs` / the selected `run`, so a streaming turn and
 * its history stay in sync without any region knowing about the stream itself.
 */
export function Workbench() {
  const { runs, run, activeRunId, streamingRunId, selectRun, newConversation, view } = useWorkbench();

  // Newest turn first in the rail.
  const items: ConversationSummary[] = [...runs]
    .reverse()
    .map((r) => ({
      id: r.id,
      title: r.question || "New conversation",
      mode: r.mode,
      timeLabel: relTime(r.createdAt),
      group: "This session",
      active: r.id === activeRunId,
    }));

  const activeTitle = run.question || "New conversation";

  return (
    <>
      <AppShell
        header={<HeaderBar liveSources={run.liveSources} />}
        left={
          <ConversationsPanel
            conversations={items}
            onSelect={selectRun}
            onNew={newConversation}
          />
        }
        center={
          view === "graphs" ? (
            <GraphExplorer />
          ) : view === "evaluation" ? (
            <EvaluationDashboard />
          ) : (
            <ChatThread
              title={activeTitle}
              runs={runs}
              activeRun={run}
              activeRunId={activeRunId}
              streamingRunId={streamingRunId}
              onSelectRun={selectRun}
            />
          )
        }
        inspector={<InspectorPanel run={run} />}
        inspectorDrawer={<InspectorDrawer run={run} />}
        hideRails={view === "graphs" || view === "evaluation"}
      />
      <SettingsPanel />
    </>
  );
}
