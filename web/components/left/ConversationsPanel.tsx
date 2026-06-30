import type { ConversationSummary } from "@/lib/types";
import { PlusIcon } from "@/components/ui/icons";
import { ConversationItem } from "./ConversationItem";

/** Group conversations by their `group` label, preserving first-seen order. */
function groupConversations(convos: ConversationSummary[]) {
  const groups: { label: string; items: ConversationSummary[] }[] = [];
  for (const convo of convos) {
    let group = groups.find((g) => g.label === convo.group);
    if (!group) {
      group = { label: convo.group, items: [] };
      groups.push(group);
    }
    group.items.push(convo);
  }
  return groups;
}

interface ConversationsPanelProps {
  conversations: ConversationSummary[];
  onSelect?: (id: string) => void;
  onNew?: () => void;
}

export function ConversationsPanel({ conversations, onSelect, onNew }: ConversationsPanelProps) {
  const groups = groupConversations(conversations);

  return (
    <div className="flex min-h-0 flex-1 flex-col px-3.5 pb-4 pt-[18px]">
      <div className="flex items-center justify-between px-0.5 pb-4">
        <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
          Conversations
        </span>
        <button
          type="button"
          onClick={onNew}
          className="flex items-center gap-[5px] rounded-[7px] border-0 px-[9px] py-[5px] font-mono text-[11px] text-primary transition-colors"
          style={{ background: "rgba(78,158,150,0.1)", boxShadow: "rgba(78,158,150,0.35) 0 0 0 1px" }}
        >
          <PlusIcon />
          New
        </button>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-px overflow-y-auto pr-0.5">
        {conversations.length === 0 && (
          <p className="px-1 pt-2 font-mono text-[11px] leading-relaxed text-text-dim">
            No turns yet — ask a question to start.
          </p>
        )}
        {groups.map((group) => (
          <div key={group.label}>
            <div className="px-1 pb-2 pt-3 font-mono text-[9.5px] uppercase tracking-[0.1em] text-text-dim">
              {group.label}
            </div>
            {group.items.map((convo) => (
              <ConversationItem
                key={convo.id}
                convo={convo}
                onClick={onSelect ? () => onSelect(convo.id) : undefined}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
