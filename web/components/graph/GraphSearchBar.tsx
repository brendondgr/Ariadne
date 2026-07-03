"use client";

/**
 * GraphSearchBar — free-text search over node titles/descriptions and edge types.
 * The committed query updates 1 second after the user stops typing (debounced),
 * or immediately when they press Enter / click Search / clear the field.
 *
 * Remount (via a `key` on the dataset) reseeds the local text from `value`, so
 * switching datasets resets the field to that dataset's committed query.
 */

import { useCallback, useEffect, useRef, useState } from "react";

const DEBOUNCE_MS = 1000;

interface GraphSearchBarProps {
  /** The currently-committed query for this dataset (seeds the input). */
  value: string;
  /** Commit a query — filters the graph. */
  onSearch: (query: string) => void;
  disabled?: boolean;
}

export function GraphSearchBar({ value, onSearch, disabled }: GraphSearchBarProps) {
  const [text, setText] = useState(value);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  // Cancel any pending debounce on unmount.
  useEffect(() => clearTimer, [clearTimer]);

  const commit = useCallback(
    (next: string) => {
      clearTimer();
      onSearch(next.trim());
    },
    [clearTimer, onSearch],
  );

  const handleChange = (next: string) => {
    setText(next);
    clearTimer();
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      onSearch(next.trim());
    }, DEBOUNCE_MS);
  };

  const handleClear = () => {
    setText("");
    commit("");
  };

  return (
    <div
      className="flex flex-shrink-0 items-center gap-2 bg-surface px-4 py-2"
      style={{ boxShadow: "rgba(235,230,220,0.08) 0 1px 0 0" }}
    >
      <div className="relative flex min-w-0 flex-1 items-center">
        <SearchGlyph />
        <input
          type="search"
          value={text}
          disabled={disabled}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") commit(text);
            if (e.key === "Escape" && text) handleClear();
          }}
          placeholder="Search nodes by name or description, edges by type…"
          aria-label="Search the graph"
          className="min-w-0 flex-1 rounded-md border-0 bg-console py-1.5 pl-8 pr-8 font-mono text-[12px] text-text-soft placeholder:text-text-faint focus-visible:outline-none"
          style={{ boxShadow: "rgba(235,230,220,0.1) 0 0 0 1px" }}
        />
        {text && (
          <button
            type="button"
            onClick={handleClear}
            aria-label="Clear search"
            className="absolute right-2 flex h-5 w-5 items-center justify-center rounded border-0 bg-transparent text-text-muted transition-colors hover:text-primary focus-visible:outline-none"
          >
            ✕
          </button>
        )}
      </div>
      <button
        type="button"
        onClick={() => commit(text)}
        disabled={disabled}
        className="flex-shrink-0 rounded-md px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.06em] transition-opacity hover:opacity-90 focus-visible:outline-none disabled:opacity-40"
        style={{ background: "var(--color-primary)", color: "var(--color-bg)" }}
      >
        Search
      </button>
    </div>
  );
}

function SearchGlyph() {
  return (
    <svg
      width={13}
      height={13}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className="pointer-events-none absolute left-2.5"
      style={{ color: "var(--color-text-muted)" }}
    >
      <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="1.8" />
      <path d="M20 20l-3.5-3.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
