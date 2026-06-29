"use client";

import { useWorkbench, type InspectorTab } from "@/components/workbench/WorkbenchContext";

const TABS: { key: InspectorTab; label: string }[] = [
  { key: "trace", label: "Trace" },
  { key: "evidence", label: "Evidence" },
  { key: "join", label: "Join Index" },
  { key: "raw", label: "Raw JSON" },
];

export function InspectorTabs() {
  const { activeTab, setActiveTab } = useWorkbench();
  return (
    <div className="flex gap-0.5">
      {TABS.map((tab) => {
        const active = activeTab === tab.key;
        return (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            aria-pressed={active}
            className={`cursor-pointer rounded-t-[7px] border-0 px-3 py-[7px] font-mono text-[11px] tracking-[0.03em] transition-colors ${
              active ? "bg-bg text-primary" : "bg-transparent text-text-muted hover:text-text"
            }`}
            style={active ? { boxShadow: "rgba(78,158,150,0.35) 0 -2px 0 0 inset" } : undefined}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
