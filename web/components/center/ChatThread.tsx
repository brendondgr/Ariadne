import type { WorkbenchRun } from "@/lib/types";
import { ThreadHeader } from "./ThreadHeader";
import { UserMessage } from "./UserMessage";
import { AnswerCard } from "./AnswerCard";
import { Composer } from "./Composer";

interface ChatThreadProps {
  title: string;
  /** Every turn in the conversation, oldest first. */
  runs: WorkbenchRun[];
  /** The selected turn (drives the title strip + inspector elsewhere). */
  activeRun: WorkbenchRun;
  activeRunId: string;
  /** The turn currently streaming, or null when idle. */
  streamingRunId: string | null;
  onSelectRun: (id: string) => void;
}

/** A question + its answer card. Clicking anywhere selects the turn so the
 *  inspector follows it. Only the streaming turn animates (`live`). */
function TurnBlock({
  run,
  active,
  live,
  onSelect,
}: {
  run: WorkbenchRun;
  active: boolean;
  live: boolean;
  onSelect: () => void;
}) {
  return (
    <div
      onClick={onSelect}
      className={`flex cursor-pointer flex-col gap-[22px] rounded-[16px] p-2 transition-colors ${
        active ? "bg-[rgba(78,158,150,0.05)]" : "hover:bg-[rgba(235,230,220,0.02)]"
      }`}
    >
      <UserMessage text={run.question} />
      <AnswerCard run={run} live={live} />
    </div>
  );
}

function EmptyThread() {
  return (
    <div className="flex flex-1 items-center justify-center">
      <p className="max-w-sm text-center font-mono text-[12px] leading-relaxed text-text-muted">
        Ask a question below to route it across the live graphs and watch the
        evidence-backed pipeline run end to end.
      </p>
    </div>
  );
}

/** The center conversation pane: title strip, scrolling multi-turn list, and the
 *  docked composer. */
export function ChatThread({
  title,
  runs,
  activeRun,
  activeRunId,
  streamingRunId,
  onSelectRun,
}: ChatThreadProps) {
  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <ThreadHeader title={title} run={activeRun} />
      <div className="flex flex-1 flex-col gap-3 overflow-y-auto px-[14px] pb-2 pt-6">
        {runs.length === 0 ? (
          <EmptyThread />
        ) : (
          runs.map((r) => (
            <TurnBlock
              key={r.id}
              run={r}
              active={r.id === activeRunId}
              live={r.id === streamingRunId}
              onSelect={() => onSelectRun(r.id)}
            />
          ))
        )}
      </div>
      <Composer />
    </div>
  );
}
