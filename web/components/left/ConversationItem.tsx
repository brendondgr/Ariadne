"use client";

import { useState, type KeyboardEvent } from "react";
import { PencilIcon, TrashIcon } from "@/components/ui/icons";

interface ConversationItemProps {
  id: string;
  title: string;
  active: boolean;
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
      className={`group relative flex w-full min-w-0 items-start gap-1 rounded-[10px] px-2.5 py-[7px] text-left transition-colors ${
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
        className="min-w-0 flex-1 border-0 bg-transparent p-0 text-left"
      >
        <span
          className={`line-clamp-2 text-[12.5px] leading-[1.32] ${
            active ? "font-semibold text-text" : "font-medium text-text-soft"
          }`}
        >
          {title}
        </span>
      </button>
      <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
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
