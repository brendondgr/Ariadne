import { PlayIcon } from "@/components/ui/icons";

/** Ghost header button that triggers the full `--yolo-all` pipeline (handler
 *  wired in a later phase; a confirm modal will guard the mutating op). */
export function RunPipelineButton() {
  return (
    <button
      type="button"
      className="flex items-center gap-2 rounded-lg border-0 bg-transparent px-[13px] py-2 font-mono text-xs tracking-[0.04em] text-text shadow-border-strong transition-[color,box-shadow] hover:text-primary hover:shadow-[rgba(78,158,150,0.6)_0_0_0_1px]"
    >
      <span className="text-secondary">
        <PlayIcon />
      </span>
      Run Pipeline
      <span className="font-mono text-[10px] text-text-muted">--yolo-all</span>
    </button>
  );
}
