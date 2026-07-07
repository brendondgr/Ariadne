"use client";

/** One headline metric with its sub-statistics, styled per Woven Dusk tokens. */
export function MetricCard({
  title,
  value,
  caption,
  stats,
}: {
  title: string;
  value: string;
  caption?: string;
  stats?: [string, string][];
}) {
  return (
    <div
      className="flex flex-col gap-3 rounded-lg p-4"
      style={{ boxShadow: "rgba(235,230,220,0.08) 0 0 0 1px, rgba(0,0,0,0.15) 0 2px 8px -4px" }}
    >
      <h3 className="m-0 font-mono text-[11px] uppercase tracking-[0.06em] text-text-muted">{title}</h3>
      <div className="flex items-baseline gap-2">
        <span className="font-sans text-[30px] font-semibold leading-none text-text tabular-nums">{value}</span>
      </div>
      {caption && <p className="m-0 font-sans text-[12px] leading-snug text-text-faint">{caption}</p>}
      {stats && stats.length > 0 && (
        <dl className="m-0 flex flex-wrap gap-x-5 gap-y-1.5">
          {stats.map(([label, v]) => (
            <div key={label} className="flex items-baseline gap-1.5">
              <dt className="font-mono text-[10px] uppercase tracking-[0.04em] text-text-muted">{label}</dt>
              <dd className="m-0 font-mono text-[12px] text-text-soft tabular-nums">{v}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}
