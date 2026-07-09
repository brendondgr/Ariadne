"use client";

import { useState, type KeyboardEvent } from "react";
import { PencilIcon, SwirlIcon, TrashIcon } from "@/components/ui/icons";

interface ConversationItemProps {
  id: string;
  title: string;
  active: boolean;
  /** A query is running in this chat in the background — show the swirl. */
  busy?: boolean;
  onClick?: () => void;
  onRename?: (title: string) => void;
  onDelete?: () => void;
}

/** A single compact sidebar conversation "pill". The whole row is a rounded box:
 *  the active thread gets a teal tint + ring, idle rows lighten on hover. Titles
 *  wrap to two lines instead of truncating mid-word. Hovering (or focusing) the
 *  row reveals rename/delete actions. */
export function ConversationItem({
  id,
  title,
  active,
  busy = false,
  onClick,
  onRename,
  onDelete,
}: ConversationItemProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(title);

  const startRename = () => {
    setDraft(title);
    setEditing(true);
  };

  const commitRename = () => {
    const trimmed = draft.trim();
    setEditing(false);
    if (trimmed && trimmed !== title) onRename?.(trimmed);
  };

  const onRenameKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      commitRename();
    } else if (e.key === "Escape") {
      e.preventDefault();
      setEditing(false);
    }
  };

  const confirmDelete = () => {
    if (typeof window !== "undefined" && !window.confirm(`Delete "${title}"? This cannot be undone.`)) {
      return;
    }
    onDelete?.();
  };

  if (editing) {
    return (
      <div className="rounded-[10px] bg-surface px-2.5 py-[7px]">
        <input
          id={`conversation-rename-${id}`}
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onRenameKeyDown}
          onBlur={commitRename}
          aria-label="Rename conversation"
          className="w-full rounded-[6px] border-0 bg-[rgba(236,235,232,0.06)] px-2 py-1 text-[12.5px] font-semibold text-text outline-none"
        />
      </div>
    );
  }

  return (
    <div
      className={`group relative w-full min-w-0 rounded-[10px] px-2.5 py-[7px] text-left transition-colors ${
        active ? "text-text" : "hover:bg-[rgba(236,235,232,0.04)]"
      }`}
      style={
        active
          ? { background: "rgba(78,158,150,0.1)", boxShadow: "rgba(78,158,150,0.35) 0 0 0 1px" }
          : undefined
      }
    >
      <button
        type="button"
        onClick={onClick}
        aria-current={active ? "page" : undefined}
        title={title}
        className="block w-full min-w-0 border-0 bg-transparent p-0 text-left"
      >
        {/* One line, expands to fill the row; a long title fades out at the right
            edge (mask gradient) instead of clipping to an ellipsis. */}
        <span
          className={`block w-full overflow-hidden whitespace-nowrap text-[12.5px] leading-[1.5] ${
            active ? "font-semibold text-text" : "font-medium text-text-soft"
          }`}
          style={{
            maskImage: "linear-gradient(to right, #000 80%, transparent)",
            WebkitMaskImage: "linear-gradient(to right, #000 80%, transparent)",
          }}
        >
          {title}
        </span>
      </button>

      {busy && (
        <span
          className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-primary group-hover:hidden"
          title="Query running"
        >
          <SwirlIcon size={13} />
          <span className="sr-only">Query running</span>
        </span>
      )}

      {/* Rename/delete slide over the faded end of the title on hover — the row
          reserves no space for them, so titles use the full width. The gradient
          backing blends the icons onto the row so they read over the text. */}
      <div
        className="absolute right-1 top-1/2 flex -translate-y-1/2 items-center gap-0.5 rounded-[7px] py-[3px] pl-6 pr-0.5 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100"
        style={{
          background: `linear-gradient(to right, transparent, ${
            active ? "#1d2625" : "var(--color-surface)"
          } 46%)`,
        }}
      >
        <button
          type="button"
          onClick={startRename}
          aria-label={`Rename ${title}`}
          title="Rename"
          className="flex items-center justify-center rounded-[6px] border-0 bg-transparent p-1 text-text-muted transition-colors hover:text-text"
        >
          <PencilIcon />
        </button>
        <button
          type="button"
          onClick={confirmDelete}
          aria-label={`Delete ${title}`}
          title="Delete"
          className="flex items-center justify-center rounded-[6px] border-0 bg-transparent p-1 text-text-muted transition-colors hover:text-secondary"
        >
          <TrashIcon />
        </button>
      </div>
    </div>
  );
}
