import type { ReactNode } from "react";

interface AppShellProps {
  header: ReactNode;
  left: ReactNode;
  center: ReactNode;
  right: ReactNode;
}

/**
 * Full-height three-region workbench frame. The shell itself never scrolls;
 * each region scrolls internally. Fixed widths here; responsive drawer
 * behavior is layered on in a later phase.
 */
export function AppShell({ header, left, center, right }: AppShellProps) {
  return (
    <div className="flex h-screen w-full flex-col overflow-hidden bg-bg">
      {header}
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <aside
          className="flex min-h-0 flex-[0_0_268px] flex-col bg-surface"
          style={{ boxShadow: "rgba(235,230,220,0.14) 1px 0 0 0" }}
        >
          {left}
        </aside>

        <main
          className="flex min-h-0 min-w-0 flex-1 flex-col bg-bg"
          style={{ boxShadow: "rgba(235,230,220,0.08) 1px 0 0 0" }}
        >
          {center}
        </main>

        {/* The right region owns its own <aside> so it can collapse. */}
        {right}
      </div>
    </div>
  );
}
