"use client";

/**
 * GraphSearchBar — one-line graph toolbar: a jumps (hop-depth) selector on the
 * far left, a field-scope picker, the free-text search, and the dataset's
 * node/edge counts on the right.
 *
 * The committed query updates 1 second after the user stops typing (debounced),
 * or immediately when they press Enter / click Search / clear the field.
 * Jumps + scope changes commit immediately.
 *
 * Remount (via a `key` on the dataset) reseeds the local text from `value`, so
 * switching datasets resets the field to that dataset's committed query.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { SearchField } from "@/lib/graph";
import { ALL_SEARCH_FIELDS } from "@/lib/graph";

const DEBOUNCE_MS = 1000;

/** Hop-depth choices: 0 = matches only, N = matches + everything within N jumps. */
const HOP_OPTIONS = [0, 1, 2, 3] as const;

const FIELD_LABELS: Record<SearchField, string> = {
  name: "Name",
  id: "ID",
  description: "Description",
  label: "Label",
  type: "Edge type",
};

interface GraphSearchBarProps {
  /** The currently-committed query for this dataset (seeds the input). */
  value: string;
  /** Commit a query — filters the graph. */
  onSearch: (query: string) => void;
  /** Neighborhood reach around matches, in jumps (0 = matches only). */
  hops: number;
  onHopsChange: (hops: number) => void;
  /** Which fields the query matches against (always at least one). */
  fields: ReadonlySet<SearchField>;
  onFieldsChange: (fields: Set<SearchField>) => void;
  /** Dataset totals shown at the right end of the line. */
  counts: { nodes: number; relationships: number } | null;
  disabled?: boolean;
}

export function GraphSearchBar({
  value,
  onSearch,
  hops,
  onHopsChange,
  fields,
  onFieldsChange,
  counts,
  disabled,
}: GraphSearchBarProps) {
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

  const countSummary = counts
    ? `${counts.nodes.toLocaleString()} nodes · ${counts.relationships.toLocaleString()} edges`
    : "—";

  return (
    <div
      className="flex flex-shrink-0 items-center gap-2 bg-surface px-4 py-2"
      style={{ boxShadow: "rgba(235,230,220,0.08) 0 1px 0 0" }}
    >
      {/* Jumps — how far past the matches the view reaches */}
      <label className="flex flex-shrink-0 items-center gap-1.5">
        <span
          className="font-mono text-[10px] uppercase tracking-[0.08em]"
          style={{ color: "var(--color-text-muted)" }}
        >
          Jumps
        </span>
        <select
          value={hops}
          disabled={disabled}
          onChange={(e) => onHopsChange(Number(e.target.value))}
          aria-label="Show nodes within this many jumps of a match"
          className="rounded-md border-0 bg-console py-1.5 pl-2 pr-1 font-mono text-[12px] text-text-soft focus-visible:outline-none disabled:opacity-40"
          style={{ boxShadow: "rgba(235,230,220,0.1) 0 0 0 1px" }}
        >
          {HOP_OPTIONS.map((n) => (
            <option key={n} value={n}>
              {n === 0 ? "Matches only" : `Within ${n} jump${n > 1 ? "s" : ""}`}
            </option>
          ))}
        </select>
      </label>

      {/* Field scope — which portions of the graph text the query matches */}
      <FieldScopePicker fields={fields} onFieldsChange={onFieldsChange} disabled={disabled} />

      {/* Free-text search */}
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
          placeholder="Search the graph…"
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

      {/* Node/edge counts — same line as the search, right-aligned */}
      <span
        className="flex-shrink-0 pl-1 font-mono text-[11px] tabular-nums"
        style={{ color: "var(--color-text-muted)", fontFeatureSettings: '"tnum"' }}
      >
        {countSummary}
      </span>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Field-scope picker                                                          */
/* -------------------------------------------------------------------------- */

function scopeSummary(fields: ReadonlySet<SearchField>): string {
  if (fields.size >= ALL_SEARCH_FIELDS.length) return "All fields";
  const active = ALL_SEARCH_FIELDS.filter((f) => fields.has(f)).map((f) => FIELD_LABELS[f]);
  if (active.length <= 2) return active.join(" + ");
  return `${active[0]} +${active.length - 1}`;
}

function FieldScopePicker({
  fields,
  onFieldsChange,
  disabled,
}: {
  fields: ReadonlySet<SearchField>;
  onFieldsChange: (fields: Set<SearchField>) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);

  const toggle = (field: SearchField) => {
    const next = new Set(fields);
    if (next.has(field)) next.delete(field);
    else next.add(field);
    // Keep at least one field active — an empty scope would match nothing
    // the analyst can predict.
    if (next.size === 0) return;
    onFieldsChange(next);
  };

  return (
    <div className="relative flex-shrink-0">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="true"
        aria-expanded={open}
        aria-label="Choose which fields the search matches"
        className="flex items-center gap-1.5 rounded-md bg-console py-1.5 pl-2.5 pr-2 font-mono text-[12px] text-text-soft transition-colors focus-visible:outline-none disabled:opacity-40"
        style={{ boxShadow: "rgba(235,230,220,0.1) 0 0 0 1px" }}
      >
        <span
          className="font-mono text-[10px] uppercase tracking-[0.08em]"
          style={{ color: "var(--color-text-muted)" }}
        >
          In
        </span>
        {scopeSummary(fields)}
        <svg width={9} height={9} viewBox="0 0 24 24" fill="none" aria-hidden="true" style={{ color: "var(--color-text-muted)" }}>
          <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && (
        <>
          {/* Click-away backdrop */}
          <div className="fixed inset-0 z-20" onClick={() => setOpen(false)} aria-hidden="true" />
          <div
            role="group"
            aria-label="Search fields"
            className="absolute left-0 top-full z-30 mt-1 flex min-w-[172px] flex-col gap-0.5 rounded-md bg-console p-1.5"
            style={{
              boxShadow:
                "rgba(235,230,220,0.12) 0 0 0 1px, rgba(0,0,0,0.35) 0 6px 18px",
            }}
            onKeyDown={(e) => {
              if (e.key === "Escape") setOpen(false);
            }}
          >
            {ALL_SEARCH_FIELDS.map((field) => {
              const active = fields.has(field);
              return (
                <label
                  key={field}
                  className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 font-mono text-[12px] transition-colors hover:bg-surface"
                  style={{ color: active ? "var(--color-text-soft)" : "var(--color-text-muted)" }}
                >
                  <input
                    type="checkbox"
                    checked={active}
                    onChange={() => toggle(field)}
                    className="h-3 w-3 accent-[var(--color-primary)]"
                  />
                  {FIELD_LABELS[field]}
                </label>
              );
            })}
          </div>
        </>
      )}
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
