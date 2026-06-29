import type { WorkbenchRun } from "@/lib/types";

/** Whole-run progress summary above the inspector body. */
export function ProgressMeter({ run }: { run: WorkbenchRun }) {
  const stages = run.plannerStages.length;
  const specialists = run.lanes.length;
  const done = run.status !== "running" && run.status !== "idle";

  return (
    <div
      className="flex-[0_0_auto] px-4 pb-3 pt-[11px]"
      style={{ boxShadow: "rgba(235,230,220,0.08) 0 1px 0 0" }}
    >
      <div className="mb-[7px] flex items-center justify-between">
        <span className="font-mono text-[11px] text-text-muted">
          {stages} / {stages} stages · {specialists} specialists complete
        </span>
        <span className="font-mono text-[11px] text-primary">
          {done ? "done" : "running"} · {run.elapsedMs}ms
        </span>
      </div>
      <div className="h-1 overflow-hidden rounded-full bg-[rgba(235,230,220,0.08)]">
        <div
          className="h-full rounded-full"
          style={{ width: "100%", background: "linear-gradient(90deg,#8A9E98,#4E9E96)" }}
        />
      </div>
    </div>
  );
}
