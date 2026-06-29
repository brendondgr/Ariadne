import type { LiveSource } from "@/lib/types";
import { ThreadGlyph, UserIcon } from "@/components/ui/icons";
import { InfraStatusPill } from "./InfraStatusPill";
import { RunPipelineButton } from "./RunPipelineButton";

interface HeaderBarProps {
  liveSources: LiveSource[];
}

/** Sticky top bar: wordmark + thread glyph, live infra status pills, the
 *  Run Pipeline action, and the Neo4j credentials entry point. */
export function HeaderBar({ liveSources }: HeaderBarProps) {
  return (
    <header
      className="z-[5] flex h-[58px] flex-[0_0_auto] items-center gap-[18px] bg-surface px-[18px]"
      style={{ boxShadow: "rgba(235,230,220,0.14) 0 1px 0 0" }}
    >
      <div className="flex items-center gap-[11px]">
        <ThreadGlyph />
        <span className="text-lg font-semibold tracking-[-0.5px]">Ariadne</span>
        <span
          className="ml-0.5 rounded-full px-[7px] py-0.5 font-mono text-[10px] uppercase tracking-[0.12em] text-text-muted shadow-border"
        >
          Analyst Workbench
        </span>
      </div>

      <div className="ml-1.5 flex items-center gap-[9px]">
        {liveSources.map((source) => (
          <InfraStatusPill key={source.backend} source={source} />
        ))}
      </div>

      <div className="flex-1" />

      <RunPipelineButton />
      <button
        type="button"
        title="Neo4j login / credentials"
        aria-label="Neo4j login and credentials"
        className="flex h-9 w-9 items-center justify-center rounded-lg border-0 bg-transparent text-text-muted shadow-border-strong transition-[box-shadow] hover:shadow-[rgba(78,158,150,0.6)_0_0_0_1px]"
      >
        <UserIcon />
      </button>
    </header>
  );
}
