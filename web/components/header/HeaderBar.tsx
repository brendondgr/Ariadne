"use client";

import type { LiveSource } from "@/lib/types";
import { GearIcon } from "@/components/ui/icons";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";
import { InfraStatusBar } from "./InfraStatusBar";
import { RunPipelineButton } from "./RunPipelineButton";
import { MobileMenuButton } from "./MobileMenuButton";
import { ViewToggle } from "./ViewToggle";

interface HeaderBarProps {
  liveSources: LiveSource[];
}

/** Sticky top bar: wordmark + thread glyph, live infra status pills (polled),
 *  the Run Pipeline action, and the Settings entry point. */
export function HeaderBar({ liveSources }: HeaderBarProps) {
  const { openSettings } = useWorkbench();

  return (
    <header
      className="z-[5] flex h-[58px] flex-[0_0_auto] items-center gap-3 bg-surface px-3 sm:gap-[18px] sm:px-[18px]"
      style={{ boxShadow: "rgba(235,230,220,0.14) 0 1px 0 0" }}
    >
      <MobileMenuButton />

      <div className="flex items-center gap-[11px]">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/ariadne-logo.svg"
          alt="Ariadne"
          width={30}
          height={26}
          className="h-[26px] w-auto select-none"
          draggable={false}
        />
        <span className="text-lg font-semibold tracking-[-0.5px]">Ariadne</span>
      </div>

      <ViewToggle />

      <div className="flex-1" />

      <div className="hidden items-center gap-[9px] md:flex">
        <InfraStatusBar fallback={liveSources} />
      </div>

      <div className="hidden sm:block">
        <RunPipelineButton />
      </div>
      <button
        type="button"
        onClick={openSettings}
        title="Settings — LLM and connection configuration"
        aria-label="Open settings"
        className="flex h-9 w-9 items-center justify-center rounded-lg border-0 bg-transparent text-text-muted shadow-border-strong transition-[box-shadow,color] hover:text-primary hover:shadow-[rgba(78,158,150,0.6)_0_0_0_1px]"
      >
        <GearIcon />
      </button>
    </header>
  );
}
