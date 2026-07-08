import type { Accent } from "./types";

/**
 * Shared Woven Dusk style constants. Colors live in CSS tokens (globals.css);
 * these capture the exact rgba tints and multi-layer shadow stacks from the
 * mockup that are awkward to express as Tailwind utilities.
 */

export const CONSOLE_BG = "#15191a";

export const SHADOW = {
  border: "rgba(235,230,220,0.08) 0 0 0 1px",
  borderStrong: "rgba(235,230,220,0.14) 0 0 0 1px",
  lightRing: "rgba(235,230,220,0.12) 0 0 0 1px",
  hairline: "rgba(235,230,220,0.07) 0 0 0 1px",
  answerCard:
    "rgba(235,230,220,0.09) 0 0 0 1px, 0 1px 2px rgba(0,0,0,0.35), 0 10px 30px rgba(0,0,0,0.22), inset 0 1px 0 rgba(235,230,220,0.05)",
  composer: "rgba(235,230,220,0.1) 0 0 0 1px, 0 4px 16px rgba(0,0,0,0.2)",
  insetTop: "rgba(235,230,220,0.07) 0 -1px 0 0 inset",
  insetBottom: "rgba(235,230,220,0.07) 0 1px 0 0 inset",
} as const;

export interface AccentTokens {
  fg: string;
  tintBg: string;
  tintBgStrong: string;
  ring: string;
}

export const ACCENT: Record<Accent, AccentTokens> = {
  teal: {
    fg: "#4e9e96",
    tintBg: "rgba(78,158,150,0.12)",
    tintBgStrong: "rgba(78,158,150,0.16)",
    ring: "rgba(78,158,150,0.35)",
  },
  amber: {
    fg: "#c9924a",
    tintBg: "rgba(201,146,74,0.12)",
    tintBgStrong: "rgba(201,146,74,0.18)",
    ring: "rgba(201,146,74,0.3)",
  },
  sage: {
    fg: "#8a9e98",
    tintBg: "rgba(138,158,152,0.1)",
    tintBgStrong: "rgba(138,158,152,0.16)",
    ring: "rgba(138,158,152,0.3)",
  },
};

/** Milliseconds → a compact seconds label: `26.2s`, `1.3s`, `0.05s`. */
export function formatSeconds(ms: number): string {
  const s = ms / 1000;
  return `${s >= 1 ? s.toFixed(1) : s.toFixed(2)}s`;
}

/** Map a {@link StageStatus} to its display accent. */
export function statusAccent(
  status: "pending" | "running" | "pass" | "partial" | "fail",
): Accent {
  if (status === "partial") return "amber";
  if (status === "fail") return "amber";
  return status === "pending" ? "sage" : "teal";
}

/** Sidebar date bucket for a conversation, computed from `updated_at`. */
export type DateBucket = "Today" | "Yesterday" | "Previous 7 days" | "Older";

/** Bucket an ISO timestamp relative to `now` (defaults to `Date.now()`) into
 *  one of the sidebar's real date groups. Falls back to "Older" for an
 *  unparsable timestamp so a malformed row never throws. */
export function dateBucket(isoTimestamp: string, now: number = Date.now()): DateBucket {
  const ts = Date.parse(isoTimestamp);
  if (!Number.isFinite(ts)) return "Older";

  const startOfDay = (ms: number) => {
    const d = new Date(ms);
    d.setHours(0, 0, 0, 0);
    return d.getTime();
  };

  const todayStart = startOfDay(now);
  const dayStart = startOfDay(ts);
  const diffDays = Math.round((todayStart - dayStart) / 86_400_000);

  if (diffDays <= 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays <= 7) return "Previous 7 days";
  return "Older";
}

/** Compact relative-time label for a conversation row ("2m ago", "3h ago",
 *  falling back to a short date past a week). */
export function relativeTimeLabel(isoTimestamp: string, now: number = Date.now()): string {
  const ts = Date.parse(isoTimestamp);
  if (!Number.isFinite(ts)) return "";
  const s = Math.max(0, Math.round((now - ts) / 1000));
  if (s < 5) return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  if (d < 7) return `${d}d ago`;
  return new Date(ts).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
