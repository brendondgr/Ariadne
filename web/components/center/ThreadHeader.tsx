import type { WorkbenchRun } from "@/lib/types";
import { Pill } from "@/components/ui/Pill";

interface ThreadHeaderProps {
  title: string;
  run: WorkbenchRun;
}

/** Center-pane title strip: conversation title + the run's mode/drafter tag. */
export function ThreadHeader({ title, run }: ThreadHeaderProps) {
  const modeLabel = run.mode === "query" ? "Full answer" : "Plan only";
  return (
    <div
      className="flex flex-[0_0_auto] items-center gap-2.5 px-[22px] py-[13px]"
      style={{ boxShadow: "rgba(235,230,220,0.08) 0 1px 0 0" }}
    >
      <span className="text-sm font-semibold">{title}</span>
      <Pill accent="teal" className="px-2 py-0.5 text-[9.5px] tracking-[0.06em]">
        {modeLabel} · {run.drafter}
      </Pill>
    </div>
  );
}
