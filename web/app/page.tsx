import { AppShell } from "@/components/shell/AppShell";
import { HeaderBar } from "@/components/header/HeaderBar";
import { ConversationsPanel } from "@/components/left/ConversationsPanel";
import { ChatThread } from "@/components/center/ChatThread";
import { InspectorPanel } from "@/components/inspector/InspectorPanel";
import { InspectorDrawer } from "@/components/inspector/InspectorDrawer";
import { WorkbenchProvider } from "@/components/workbench/WorkbenchContext";
import { wmiCapecRun } from "@/lib/fixtures";
import { conversations } from "@/lib/conversations";

export default function Page() {
  const run = wmiCapecRun;
  const activeTitle = conversations.find((c) => c.active)?.title ?? "Conversation";

  return (
    <WorkbenchProvider>
      <AppShell
        header={<HeaderBar liveSources={run.liveSources} />}
        left={<ConversationsPanel conversations={conversations} />}
        center={<ChatThread title={activeTitle} run={run} />}
        inspector={<InspectorPanel run={run} />}
        inspectorDrawer={<InspectorDrawer run={run} />}
      />
    </WorkbenchProvider>
  );
}
