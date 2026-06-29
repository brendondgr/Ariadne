import type { LiveSource } from "@/lib/types";
import { ACCENT } from "@/lib/ui";
import { StatusDot } from "@/components/ui/StatusDot";

const STATE_LABEL: Record<LiveSource["status"], string> = {
  live: "LIVE",
  down: "DOWN",
  starting: "STARTING…",
};

/** Header infra pill — e.g. `NEO4J  LIVE · 12,540`. Doubles as the entry point
 *  to infra controls (wired in a later phase). */
export function InfraStatusPill({ source }: { source: LiveSource }) {
  const accent = source.status === "down" ? "amber" : "teal";
  const a = ACCENT[accent];
  const stageStatus =
    source.status === "live" ? "pass" : source.status === "down" ? "fail" : "running";

  const detail =
    source.status === "live"
      ? `${STATE_LABEL.live} · ${source.nodes?.toLocaleString() ?? "—"}`
      : source.status === "down"
        ? `${STATE_LABEL.down}${source.reason ? ` · ${source.reason}` : ""}`
        : STATE_LABEL.starting;

  return (
    <div
      title={`${source.backend} · ${
        source.status === "live" ? `${source.nodes?.toLocaleString()} nodes loaded` : source.status
      }`}
      className="flex items-center gap-[7px] rounded-full py-1 pl-[9px] pr-[11px]"
      style={{ background: a.tintBg, boxShadow: `${a.ring} 0 0 0 1px` }}
    >
      <StatusDot status={stageStatus} pulse={source.status !== "down"} />
      <span className="font-mono text-[11px] tracking-[0.04em] text-text">
        {source.backend.toUpperCase()}
      </span>
      <span className="font-mono text-[11px]" style={{ color: a.fg }}>
        {detail}
      </span>
    </div>
  );
}
