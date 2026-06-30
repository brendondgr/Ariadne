"use client";

import { AppShell } from "@/components/shell/AppShell";
import { HeaderBar } from "@/components/header/HeaderBar";
import { ConversationsPanel } from "@/components/left/ConversationsPanel";
import { ChatThread } from "@/components/center/ChatThread";
import { InspectorPanel } from "@/components/inspector/InspectorPanel";
import { InspectorDrawer } from "@/components/inspector/InspectorDrawer";
import { SettingsPanel } from "@/components/settings/SettingsPanel";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";
import { conversations } from "@/lib/conversations";

/**
 * Client orchestrator: reads the live {@link WorkbenchRun} from the run machine
 * and feeds it to the three regions as props. Keeping this one component as the
 * single context→props bridge lets every presentational region stay unchanged
 * as the run updates while a query streams.
 */
export function Workbench() {
  const { run } = useWorkbench();
  const activeTitle = conversations.find((c) => c.active)?.title ?? "Conversation";

  return (
    <>
      <AppShell
        header={<HeaderBar liveSources={run.liveSources} />}
        left={<ConversationsPanel conversations={conversations} />}
        center={<ChatThread title={activeTitle} run={run} />}
        inspector={<InspectorPanel run={run} />}
        inspectorDrawer={<InspectorDrawer run={run} />}
      />
      <SettingsPanel />
    </>
  );
}
