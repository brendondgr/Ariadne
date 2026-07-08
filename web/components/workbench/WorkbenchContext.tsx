"use client";

import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { MotionConfig } from "motion/react";
import { useRunMachine, type RunMachine } from "@/lib/runMachine";
import type { GraphDataset } from "@/lib/types";

export type InspectorTab = "trace" | "evidence" | "join" | "raw";

interface WorkbenchState extends RunMachine {
  activeTab: InspectorTab;
  setActiveTab: (tab: InspectorTab) => void;
  /** Inspector stage/lane id requested for focus (from a chip or stepper). */
  focusStageId: string | null;
  /** Monotonic counter so repeat clicks on the same id still re-trigger focus. */
  focusNonce: number;
  focusStage: (id: string) => void;
  /** Desktop (lg+) inline inspector open/collapsed. */
  inspectorOpen: boolean;
  setInspectorOpen: (open: boolean) => void;
  /** Mobile/tablet (<lg) inspector slide-over. Defaults closed. */
  drawerOpen: boolean;
  setDrawerOpen: (open: boolean) => void;
  /** Reveal the inspector on whichever layout is active. */
  openInspector: () => void;
  /** Mobile (<md) conversations drawer. */
  leftOpen: boolean;
  setLeftOpen: (open: boolean) => void;
  /** Settings panel (LLM + connection config) open state. */
  settingsOpen: boolean;
  setSettingsOpen: (open: boolean) => void;
  openSettings: () => void;
  /** App-wide view toggle: chat workbench, graphs explorer, or evaluation. */
  view: "chat" | "graphs" | "evaluation";
  setView: (v: "chat" | "graphs" | "evaluation") => void;
  /** Active graph dataset selection. */
  graphDataset: GraphDataset;
  setGraphDataset: (d: GraphDataset) => void;
  /** Pre-fill the composer input with `text` and focus it (does not send).
   *  Used by clicked references in an answer to seed a follow-up question. */
  setComposerDraft: (text: string) => void;
  /** The composer registers its fill handler here on mount; `setComposerDraft`
   *  invokes it. An imperative channel (not derived state) so a click event
   *  drives the input without the composer syncing via a state-in-effect. */
  registerComposerFill: (fn: ((text: string) => void) | null) => void;
}

const WorkbenchCtx = createContext<WorkbenchState | null>(null);

export function WorkbenchProvider({ children }: { children: ReactNode }) {
  const [activeTab, setActiveTab] = useState<InspectorTab>("trace");
  const [focusStageId, setFocusStageId] = useState<string | null>(null);
  const [focusNonce, setFocusNonce] = useState(0);
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [leftOpen, setLeftOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [view, setView] = useState<"chat" | "graphs" | "evaluation">("chat");
  const [graphDataset, setGraphDataset] = useState<GraphDataset>("attack");
  const composerFillRef = useRef<((text: string) => void) | null>(null);
  const machine = useRunMachine();

  const registerComposerFill = useCallback((fn: ((text: string) => void) | null) => {
    composerFillRef.current = fn;
  }, []);
  const setComposerDraft = useCallback((text: string) => {
    composerFillRef.current?.(text);
  }, []);

  const openInspector = useCallback(() => {
    setInspectorOpen(true);
    setDrawerOpen(true);
  }, []);

  const openSettings = useCallback(() => setSettingsOpen(true), []);

  const focusStage = useCallback(
    (id: string) => {
      setActiveTab("trace");
      setFocusStageId(id);
      setFocusNonce((n) => n + 1);
      openInspector();
    },
    [openInspector],
  );

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
      drawerOpen,
      setDrawerOpen,
      openInspector,
      leftOpen,
      setLeftOpen,
      settingsOpen,
      setSettingsOpen,
      openSettings,
      view,
      setView,
      graphDataset,
      setGraphDataset,
      setComposerDraft,
      registerComposerFill,
    }),
    [machine, activeTab, focusStageId, focusNonce, focusStage, inspectorOpen, drawerOpen, openInspector, leftOpen, settingsOpen, openSettings, view, graphDataset, setComposerDraft, registerComposerFill],
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
