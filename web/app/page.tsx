import { AppShell } from "@/components/shell/AppShell";
import { HeaderBar } from "@/components/header/HeaderBar";
import { ConversationsPanel } from "@/components/left/ConversationsPanel";
import { ChatThread } from "@/components/center/ChatThread";
import { WorkbenchProvider } from "@/components/workbench/WorkbenchContext";
import { wmiCapecRun } from "@/lib/fixtures";
import { conversations } from "@/lib/conversations";

/** Placeholder region used until phase 5 fills the inspector. */
function RegionStub({ label }: { label: string }) {
  return (
    <div className="flex flex-1 items-center justify-center p-6">
      <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
        {label}
      </span>
    </div>
  );
}

export default function Page() {
  const run = wmiCapecRun;
  const activeTitle = conversations.find((c) => c.active)?.title ?? "Conversation";

  return (
    <WorkbenchProvider>
      <AppShell
        header={<HeaderBar liveSources={run.liveSources} />}
        left={<ConversationsPanel conversations={conversations} />}
        center={<ChatThread title={activeTitle} run={run} />}
        right={<RegionStub label="Inspector" />}
      />
    </WorkbenchProvider>
  );
}
