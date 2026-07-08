import type { ConversationSummaryDTO } from "@/lib/types";
import { dateBucket, relativeTimeLabel, type DateBucket } from "@/lib/ui";
import { PlusIcon } from "@/components/ui/icons";
import { ConversationItem } from "./ConversationItem";

const BUCKET_ORDER: DateBucket[] = ["Today", "Yesterday", "Previous 7 days", "Older"];

/** Group persisted threads into real date buckets by `updated_at`, in the
 *  canonical Today → Yesterday → Previous 7 days → Older order. Buckets with
 *  no threads are omitted. */
function groupByDate(conversations: ConversationSummaryDTO[]) {
  const byBucket = new Map<DateBucket, ConversationSummaryDTO[]>();
  for (const convo of conversations) {
    const bucket = dateBucket(convo.updated_at);
    const list = byBucket.get(bucket);
    if (list) list.push(convo);
    else byBucket.set(bucket, [convo]);
  }
  return BUCKET_ORDER.filter((b) => byBucket.has(b)).map((label) => ({
    label,
    items: byBucket.get(label)!,
  }));
}

interface ConversationsPanelProps {
  conversations: ConversationSummaryDTO[];
  activeId: string;
  loading?: boolean;
  onSelect?: (id: string) => void;
  onNew?: () => void;
  onRename?: (id: string, title: string) => void;
  onDelete?: (id: string) => void;
}

export function ConversationsPanel({
  conversations,
  activeId,
  loading = false,
  onSelect,
  onNew,
  onRename,
  onDelete,
}: ConversationsPanelProps) {
  const groups = groupByDate(conversations);

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
        {loading && conversations.length === 0 && (
          <p className="px-1 pt-2 font-mono text-[11px] leading-relaxed text-text-dim">
            Loading conversations…
          </p>
        )}
        {!loading && conversations.length === 0 && (
          <p className="px-1 pt-2 font-mono text-[11px] leading-relaxed text-text-dim">
            No conversations yet — ask a question to start one.
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
                id={convo.id}
                title={convo.title}
                timeLabel={relativeTimeLabel(convo.updated_at)}
                turnCount={convo.turn_count}
                active={convo.id === activeId}
                onClick={onSelect ? () => onSelect(convo.id) : undefined}
                onRename={onRename ? (title) => onRename(convo.id, title) : undefined}
                onDelete={onDelete ? () => onDelete(convo.id) : undefined}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
