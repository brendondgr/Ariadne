import type { CSSProperties } from "react";
import type { StageStatus } from "@/lib/types";
import { ACCENT, statusAccent } from "@/lib/ui";

interface StatusDotProps {
  status: StageStatus;
  size?: number;
  /** Pulse while live/running (CSS fallback; Motion takes over in the run view). */
  pulse?: boolean;
  className?: string;
  style?: CSSProperties;
}

/** A small round status indicator. Color is paired with status meaning; the
 *  consuming row always also carries a text/icon label (never color alone). */
export function StatusDot({ status, size = 7, pulse, className = "", style }: StatusDotProps) {
  const color = ACCENT[statusAccent(status)].fg;
  const animate = pulse ?? status === "running";
  return (
    <span
      aria-hidden
      className={`${animate ? "animate-pulse-dot" : ""} ${className}`}
      style={{
        width: size,
        height: size,
        borderRadius: "9999px",
        background: color,
        display: "inline-block",
        flex: "0 0 auto",
        ...style,
      }}
    />
  );
}
