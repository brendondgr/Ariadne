"use client";

import { AnimatePresence, motion } from "motion/react";
import type { WorkbenchRun } from "@/lib/types";
import { EASE_OUT } from "@/lib/motion";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";
import { ChevronRight } from "@/components/ui/icons";
import { InspectorContent } from "./InspectorContent";

/** Mobile/tablet (<lg) inspector as a right slide-over with backdrop, plus a
 *  floating button to reopen it when closed. */
export function InspectorDrawer({ run }: { run: WorkbenchRun }) {
  const { drawerOpen, setDrawerOpen } = useWorkbench();

  return (
    <div className="lg:hidden">
      <AnimatePresence>
        {drawerOpen && (
          <>
            <motion.div
              key="backdrop"
              className="fixed inset-0 top-[58px] z-30 bg-[rgba(14,15,17,0.6)]"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setDrawerOpen(false)}
            />
            <motion.aside
              key="panel"
              className="fixed bottom-0 right-0 top-[58px] z-40 flex w-[420px] max-w-[90vw] flex-col bg-surface"
              style={{ boxShadow: "rgba(0,0,0,0.4) -8px 0 24px" }}
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ duration: 0.3, ease: EASE_OUT }}
            >
              <InspectorContent run={run} onClose={() => setDrawerOpen(false)} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {!drawerOpen && (
        <button
          type="button"
          onClick={() => setDrawerOpen(true)}
          className="fixed bottom-5 right-5 z-30 flex items-center gap-2 rounded-full bg-primary px-4 py-2.5 font-mono text-[11px] uppercase tracking-[0.05em] text-bg shadow-card"
          aria-label="Open inspector"
        >
          <span className="rotate-180">
            <ChevronRight size={14} />
          </span>
          Inspector
        </button>
      )}
    </div>
  );
}
