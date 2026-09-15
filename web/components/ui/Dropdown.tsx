"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { SHADOW } from "@/lib/ui";

export interface DropdownOption<T> {
  value: T;
  label: string;
  /** Optional second line, shown muted under the label in the open list. */
  hint?: string;
}

/**
 * A small custom select styled for the Woven Dusk console.
 *
 * A native `<select>` renders its option list with the operating system's
 * chrome, which on a dark console reads as a light-grey box dropped onto the
 * page. This keeps the list inside the app's own palette and lets an option
 * carry a hint line — "Low · 256 tokens" — which a native option cannot.
 *
 * Closes on outside click, on Escape, and on selection; arrow keys move through
 * the list while it is open.
 */
export function Dropdown<T extends string | number>({
  value,
  options,
  onChange,
  disabled = false,
  title,
  label,
}: {
  value: T;
  options: readonly DropdownOption<T>[];
  onChange: (value: T) => void;
  disabled?: boolean;
  title?: string;
  label?: string;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const current = options.find((o) => o.value === value) ?? options[0];

  useEffect(() => {
    if (!open) return;
    const onDocDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocDown);
    return () => document.removeEventListener("mousedown", onDocDown);
  }, [open]);

  // A disabled control must not keep a stale list open beneath it.
  useEffect(() => {
    if (disabled) setOpen(false);
  }, [disabled]);

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      setOpen(false);
      return;
    }
    if (!open && (e.key === "Enter" || e.key === " " || e.key === "ArrowDown")) {
      e.preventDefault();
      setOpen(true);
      return;
    }
    if (!open) return;
    const i = options.findIndex((o) => o.value === value);
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const next = e.key === "ArrowDown"
        ? Math.min(i + 1, options.length - 1)
        : Math.max(i - 1, 0);
      onChange(options[next].value);
    }
    if (e.key === "Enter") {
      e.preventDefault();
      setOpen(false);
    }
  };

  return (
    <div ref={rootRef} className="relative" onKeyDown={onKeyDown}>
      <button
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        title={title}
        className="flex items-center gap-[7px] rounded-lg px-[11px] py-1.5 font-mono text-[11px] text-text-muted disabled:cursor-not-allowed"
        style={{ boxShadow: SHADOW.border, opacity: disabled ? 0.45 : 1 }}
      >
        {label ? <span>{label}</span> : null}
        <span className="text-[#c9c6bd]">{current?.label}</span>
        <span aria-hidden className="text-[9px] leading-none">▾</span>
      </button>

      {open && !disabled ? (
        <ul
          role="listbox"
          className="absolute bottom-[calc(100%+6px)] left-0 z-50 min-w-[168px] overflow-hidden rounded-lg py-1"
          style={{ background: "#1c1b19", boxShadow: SHADOW.border }}
        >
          {options.map((o) => {
            const selected = o.value === value;
            return (
              <li key={String(o.value)} role="option" aria-selected={selected}>
                <button
                  type="button"
                  onClick={() => {
                    onChange(o.value);
                    setOpen(false);
                  }}
                  className={`flex w-full flex-col items-start gap-[1px] px-3 py-[6px] text-left font-mono text-[11px] transition-colors ${
                    selected ? "bg-[rgba(78,158,150,0.14)] text-primary" : "text-text-muted hover:text-text"
                  }`}
                >
                  <span>{o.label}</span>
                  {o.hint ? (
                    <span className="text-[10px] text-text-faint">{o.hint}</span>
                  ) : null}
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
