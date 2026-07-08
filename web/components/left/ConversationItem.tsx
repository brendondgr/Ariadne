"use client";

import { useState, type KeyboardEvent } from "react";
import { Pill } from "@/components/ui/Pill";
import { PencilIcon, TrashIcon } from "@/components/ui/icons";

interface ConversationItemProps {
  id: string;
  title: string;
  timeLabel: string;
  turnCount: number;
  active: boolean;
  onClick?: () => void;
  onRename?: (title: string) => void;
  onDelete?: () => void;
}

/** A single sidebar conversation row backed by a persisted thread. Active rows
 *  get a teal thread-edge and a brighter title; idle rows lighten on hover.
 *  Hovering (or focusing) the row reveals rename/delete actions. */
export function ConversationItem({
  id,
  title,
  timeLabel,
  turnCount,
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
      <div className="group relative mb-0.5 flex w-full min-w-0 flex-col gap-1 rounded-[9px] bg-bg px-3 py-2.5">
        <input
          id={`conversation-rename-${id}`}
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onRenameKeyDown}
          onBlur={commitRename}
          aria-label="Rename conversation"
          className="w-full rounded-[6px] border-0 bg-[rgba(235,230,220,0.06)] px-2 py-1 text-[13px] font-semibold text-text outline-none"
        />
      </div>
    );
  }

  return (
    <div
      className={`group relative mb-0.5 flex w-full min-w-0 items-start gap-1 rounded-[9px] px-3 py-2.5 text-left transition-colors ${
        active ? "bg-bg pl-[15px]" : "hover:bg-[rgba(27,33,34,0.65)]"
      }`}
    >
      {active && (
        <span
          aria-hidden
          className="absolute bottom-2 left-0 top-2 w-[2.5px] rounded-full bg-primary"
        />
      )}
      <button
        type="button"
        onClick={onClick}
        aria-current={active ? "page" : undefined}
        className="flex min-w-0 flex-1 flex-col gap-1 border-0 bg-transparent p-0 text-left"
      >
        <span
          className={`truncate text-[13px] ${
            active ? "font-semibold text-text" : "font-medium text-[#b0ada6]"
          }`}
        >
          {title}
        </span>
        <span className="flex items-center gap-[7px]">
          <Pill accent="sage" className="px-1.5 py-px text-[9.5px] tracking-[0.06em]">
            {turnCount} turn{turnCount === 1 ? "" : "s"}
          </Pill>
          <span className="text-[11px] text-text-dim">{timeLabel}</span>
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
