import type { ConversationSummary } from "@/lib/types";
import { Pill } from "@/components/ui/Pill";

/** A single sidebar conversation row. Active rows get a teal thread-edge and a
 *  brighter title; idle rows lighten on hover. */
export function ConversationItem({ convo }: { convo: ConversationSummary }) {
  const active = !!convo.active;
  const modeAccent = convo.mode === "query" ? "teal" : "sage";
  const modeLabel = convo.mode === "query" ? "Query" : "Plan";

  return (
    <button
      type="button"
      className={`group relative mb-0.5 flex w-full flex-col gap-1 rounded-[9px] px-3 py-2.5 text-left transition-colors ${
        active ? "bg-bg pl-[15px]" : "hover:bg-[rgba(27,33,34,0.65)]"
      }`}
    >
      {active && (
        <span
          aria-hidden
          className="absolute bottom-2 left-0 top-2 w-[2.5px] rounded-full bg-primary"
        />
      )}
      <span
        className={`truncate text-[13px] ${
          active ? "font-semibold text-text" : "font-medium text-[#b0ada6]"
        }`}
      >
        {convo.title}
      </span>
      <span className="flex items-center gap-[7px]">
        <Pill accent={modeAccent} className="px-1.5 py-px text-[9.5px] tracking-[0.06em]">
          {modeLabel}
        </Pill>
        <span className="text-[11px] text-text-dim">{convo.timeLabel}</span>
      </span>
    </button>
  );
}
