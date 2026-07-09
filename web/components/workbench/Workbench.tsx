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

/**
 * Client orchestrator: reads the multi-turn conversation from the run machine
 * and feeds it to the three regions as props. The left rail lists PERSISTED
 * threads (from the backend `conversations`), the center thread + inspector
 * derive from `runs` / the selected `run` (the active thread's rehydrated or
 * streaming turns), so a streaming turn and its history stay in sync without
 * any region knowing about the stream itself.
 */
export function Workbench() {
  const {
    runs,
    run,
    activeRunId,
    streamingRunId,
    selectRun,
    view,
    conversations,
    conversationId,
    conversationsLoading,
    busyConversationIds,
    newConversation,
    selectConversation,
    renameConversation,
    deleteConversation,
  } = useWorkbench();

  const activeTitle = run.question || "New conversation";

  return (
    <>
      <AppShell
        header={<HeaderBar liveSources={run.liveSources} />}
        left={
          <ConversationsPanel
            conversations={conversations}
            activeId={conversationId}
            loading={conversationsLoading}
            busyIds={busyConversationIds}
            onSelect={(id) => void selectConversation(id)}
            onNew={() => void newConversation()}
            onRename={(id, title) => void renameConversation(id, title)}
            onDelete={(id) => void deleteConversation(id)}
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
