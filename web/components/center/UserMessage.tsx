import { SHADOW } from "@/lib/ui";

/** Right-aligned analyst question bubble. */
export function UserMessage({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div
        className="max-w-[80%] whitespace-pre-wrap break-words rounded-[13px_13px_4px_13px] bg-surface px-4 py-3 text-sm leading-[1.55] text-text"
        style={{ boxShadow: `${SHADOW.border}, inset 0 1px 0 rgba(235,230,220,0.04)` }}
      >
        {text}
      </div>
    </div>
  );
}
