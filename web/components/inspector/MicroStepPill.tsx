import type { MicroStep } from "@/lib/types";
import { ACCENT, statusAccent } from "@/lib/ui";
import { ShieldIcon } from "@/components/ui/icons";

const GLYPH: Record<MicroStep["status"], string> = {
  pending: "·",
  running: "…",
  pass: "✓",
  partial: "!",
  fail: "✕",
};

/** One of the eight specialist checkpoints. The pre-run gate and normalize —
 *  the two never-cut checkpoints — get a shield + a ringed accent. */
export function MicroStepPill({ step }: { step: MicroStep }) {
  const a = ACCENT[statusAccent(step.status)];
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-[7px] py-0.5 font-mono text-[10px]"
      style={{
        color: a.fg,
        background: step.emphasis ? a.tintBgStrong : a.tintBg,
        boxShadow: step.emphasis ? `${a.ring} 0 0 0 1px` : undefined,
      }}
    >
      {step.emphasis && <ShieldIcon size={9} />}
      {step.label} {GLYPH[step.status]}
    </span>
  );
}
