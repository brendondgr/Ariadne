"use client";

import type { ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { EASE_OUT } from "@/lib/motion";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";
import { CloseIcon } from "@/components/ui/icons";

interface AppShellProps {
  header: ReactNode;
  /** Conversations panel content, reused by the desktop rail and mobile drawer. */
  left: ReactNode;
  center: ReactNode;
  /** Desktop (lg+) inline inspector. */
  inspector: ReactNode;
  /** Mobile/tablet (<lg) inspector drawer. */
  inspectorDrawer: ReactNode;
}

/**
 * Full-height three-region workbench frame. The shell never scrolls; each
 * region scrolls internally. Below md the conversations rail becomes a
 * slide-over drawer; below lg the inspector becomes a slide-over (handled by
 * the inspectorDrawer).
 */
export function AppShell({ header, left, center, inspector, inspectorDrawer }: AppShellProps) {
  const { leftOpen, setLeftOpen } = useWorkbench();

  return (
    <div className="flex h-screen w-full flex-col overflow-hidden bg-bg">
      {header}
      <div className="flex min-h-0 flex-1 overflow-hidden">
        {/* desktop conversations rail */}
        <aside
          className="hidden min-h-0 flex-[0_0_268px] flex-col bg-surface md:flex"
          style={{ boxShadow: "rgba(235,230,220,0.14) 1px 0 0 0" }}
        >
          {left}
        </aside>

        {/* mobile conversations drawer */}
        <AnimatePresence>
          {leftOpen && (
            <>
              <motion.div
                key="left-backdrop"
                className="fixed inset-0 top-[58px] z-30 bg-[rgba(27,33,34,0.6)] md:hidden"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={() => setLeftOpen(false)}
              />
              <motion.aside
                key="left-panel"
                className="fixed bottom-0 left-0 top-[58px] z-40 flex w-[280px] max-w-[85vw] flex-col bg-surface md:hidden"
                style={{ boxShadow: "rgba(0,0,0,0.4) 8px 0 24px" }}
                initial={{ x: "-100%" }}
                animate={{ x: 0 }}
                exit={{ x: "-100%" }}
                transition={{ duration: 0.3, ease: EASE_OUT }}
              >
                <div className="flex items-center justify-end px-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setLeftOpen(false)}
                    aria-label="Close conversations"
                    className="flex h-8 w-8 items-center justify-center rounded-md border-0 bg-transparent text-text-muted hover:text-primary"
                  >
                    <CloseIcon />
                  </button>
                </div>
                <div className="min-h-0 flex-1">{left}</div>
              </motion.aside>
            </>
          )}
        </AnimatePresence>

        <main
          className="flex min-h-0 min-w-0 flex-1 flex-col bg-bg"
          style={{ boxShadow: "rgba(235,230,220,0.08) 1px 0 0 0" }}
        >
          {center}
        </main>

        {inspector}
      </div>

      {inspectorDrawer}
    </div>
  );
}
