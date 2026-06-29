"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { MotionConfig } from "motion/react";
import { useRunMachine, type RunMachine } from "@/lib/runMachine";

export type InspectorTab = "trace" | "evidence" | "join" | "raw";

interface WorkbenchState extends RunMachine {
  activeTab: InspectorTab;
  setActiveTab: (tab: InspectorTab) => void;
  /** Inspector stage/lane id requested for focus (from a chip or stepper). */
  focusStageId: string | null;
  /** Monotonic counter so repeat clicks on the same id still re-trigger focus. */
  focusNonce: number;
  focusStage: (id: string) => void;
  inspectorOpen: boolean;
  setInspectorOpen: (open: boolean) => void;
}

const WorkbenchCtx = createContext<WorkbenchState | null>(null);

export function WorkbenchProvider({ children }: { children: ReactNode }) {
  const [activeTab, setActiveTab] = useState<InspectorTab>("trace");
  const [focusStageId, setFocusStageId] = useState<string | null>(null);
  const [focusNonce, setFocusNonce] = useState(0);
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const machine = useRunMachine();

  const focusStage = useCallback((id: string) => {
    setActiveTab("trace");
    setFocusStageId(id);
    setFocusNonce((n) => n + 1);
    setInspectorOpen(true);
  }, []);

  const value = useMemo<WorkbenchState>(
    () => ({
      ...machine,
      activeTab,
      setActiveTab,
      focusStageId,
      focusNonce,
      focusStage,
      inspectorOpen,
      setInspectorOpen,
    }),
    [machine, activeTab, focusStageId, focusNonce, focusStage, inspectorOpen],
  );

  return (
    <MotionConfig reducedMotion="user">
      <WorkbenchCtx.Provider value={value}>{children}</WorkbenchCtx.Provider>
    </MotionConfig>
  );
}

export function useWorkbench(): WorkbenchState {
  const ctx = useContext(WorkbenchCtx);
  if (!ctx) throw new Error("useWorkbench must be used within WorkbenchProvider");
  return ctx;
}
