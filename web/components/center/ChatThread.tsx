import type { WorkbenchRun } from "@/lib/types";
import { ThreadHeader } from "./ThreadHeader";
import { UserMessage } from "./UserMessage";
import { AnswerCard } from "./AnswerCard";
import { Composer } from "./Composer";

interface ChatThreadProps {
  title: string;
  run: WorkbenchRun;
}

/** The center conversation pane: title strip, scrolling message list, and the
 *  docked composer. */
export function ChatThread({ title, run }: ChatThreadProps) {
  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <ThreadHeader title={title} run={run} />
      <div className="flex flex-1 flex-col gap-[22px] overflow-y-auto px-[22px] pb-2 pt-6">
        <UserMessage text={run.question} />
        <AnswerCard run={run} />
      </div>
      <Composer />
    </div>
  );
}
