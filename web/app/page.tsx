import { AppShell } from "@/components/shell/AppShell";
import { HeaderBar } from "@/components/header/HeaderBar";
import { wmiCapecRun } from "@/lib/fixtures";

/** Placeholder region used until phases 4–5 fill the rails. */
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
  return (
    <AppShell
      header={<HeaderBar liveSources={run.liveSources} />}
      left={<RegionStub label="Conversations" />}
      center={<RegionStub label="Chat thread" />}
      right={<RegionStub label="Inspector" />}
    />
  );
}
