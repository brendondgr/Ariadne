import type { CSSProperties, ReactNode } from "react";
import type { Accent } from "@/lib/types";
import { ACCENT } from "@/lib/ui";

type PillVariant = "tint" | "tintRing" | "ghost";

interface PillProps {
  accent?: Accent;
  variant?: PillVariant;
  className?: string;
  style?: CSSProperties;
  title?: string;
  children: ReactNode;
}

/**
 * Woven Dusk pill badge — mono, uppercase, 9999px radius. `tint` fills with the
 * accent's translucent background; `tintRing` adds a shadow-as-border ring;
 * `ghost` is transparent muted text.
 */
export function Pill({
  accent = "teal",
  variant = "tint",
  className = "",
  style,
  title,
  children,
}: PillProps) {
  const a = ACCENT[accent];
  const variantStyle: CSSProperties =
    variant === "ghost"
      ? { color: "var(--color-text-muted)" }
      : variant === "tintRing"
        ? { color: a.fg, background: a.tintBg, boxShadow: `${a.ring} 0 0 0 1px` }
        : { color: a.fg, background: a.tintBg };

  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1.5 rounded-full font-mono uppercase leading-none tracking-[0.06em] ${className}`}
      style={{ ...variantStyle, ...style }}
    >
      {children}
    </span>
  );
}
