"use client";

import { useEffect, useRef, useState } from "react";
import { PlayIcon } from "@/components/ui/icons";
import { streamAdmin } from "@/lib/api";
import { runYoloPipeline } from "@/lib/pipeline";
import { CONSOLE_BG, SHADOW } from "@/lib/ui";

/** Header button that triggers the full `--yolo-all` pipeline (download → build →
 *  docker → load → verify) via `POST /api/admin`. The op is mutating and host-
 *  dependent, so a confirm guards it and progress streams into a popover console. */
export function RunPipelineButton() {
  const [running, setRunning] = useState(false);
  const [open, setOpen] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [logs]);

  const run = async () => {
    if (running) return;
    if (!window.confirm("Run the full --yolo-all pipeline? This downloads, builds, and loads the graphs.")) {
      return;
    }
    setRunning(true);
    setOpen(true);
    setResult(null);
    setLogs([]);
    try {
      await runYoloPipeline(streamAdmin, {
        onLine: (line) => setLogs((l) => [...l, line]),
        onResult: setResult,
      });
    } catch (err) {
      setResult({ ok: false, message: err instanceof Error ? err.message : String(err) });
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={run}
        disabled={running}
        aria-busy={running}
        className="flex items-center gap-2 rounded-lg border-0 bg-transparent px-[13px] py-2 font-mono text-xs tracking-[0.04em] text-text shadow-border-strong transition-[color,box-shadow] hover:text-primary hover:shadow-[rgba(78,158,150,0.6)_0_0_0_1px] disabled:opacity-60"
      >
        <span className="text-secondary">
          <PlayIcon />
        </span>
        {running ? "Running…" : "Run Pipeline"}
        <span className="font-mono text-[10px] text-text-muted">--yolo-all</span>
      </button>

      {open && (logs.length > 0 || result || running) && (
        <div
          className="absolute right-0 top-[calc(100%+6px)] z-30 w-[360px] rounded-lg p-2.5"
          style={{ background: CONSOLE_BG, boxShadow: SHADOW.border }}
        >
          <div className="mb-1.5 flex items-center justify-between">
            <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-text-faint">
              --yolo-all pipeline
            </span>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="border-0 bg-transparent font-mono text-[11px] text-text-muted hover:text-text"
            >
              ✕
            </button>
          </div>
          <div
            ref={logRef}
            className="max-h-[220px] overflow-y-auto font-mono text-[11px] leading-relaxed text-text-muted"
          >
            {logs.length === 0 && !result ? (
              <div className="text-text-faint">Starting…</div>
            ) : (
              logs.map((line, i) => (
                <div key={i} className="whitespace-pre-wrap break-words">
                  {line}
                </div>
              ))
            )}
            {result && (
              <div className={`mt-1 ${result.ok ? "text-primary" : "text-secondary"}`}>
                {result.ok ? "✓ " : "✗ "}
                {result.message}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
