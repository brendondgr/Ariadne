"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ApiLlmEndpointProbe, ApiLlmTestResult } from "@/lib/types";
import { testLlm } from "@/lib/api";

/**
 * The Test button, and its verdict line.
 *
 * The server-side probe this calls sends a REAL completion rather than opening a
 * socket, because a port being open is not readiness: the record for this
 * project has ten replies arriving with no `choices` key at all while vLLM was
 * still loading weights. A TCP check and a `/models` listing both pass against
 * that server; only asking it to answer something does not.
 *
 * The failure reason is rendered verbatim. A summarized error ("connection
 * failed") is an error nobody can act on; "HTTP 404: model not found" is.
 */
export function TestConnection({ probe }: { probe: () => ApiLlmEndpointProbe }) {
  const [result, setResult] = useState<ApiLlmTestResult | null>(null);
  const [testing, setTesting] = useState(false);
  const abort = useRef<AbortController | null>(null);

  const run = useCallback(async () => {
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    setTesting(true);
    setResult(null);
    try {
      setResult(await testLlm(probe(), controller.signal));
    } catch (e) {
      if (controller.signal.aborted) return;
      setResult({
        ok: false,
        latency_ms: 0,
        model: "",
        reason: e instanceof Error ? e.message : String(e),
        summary: "",
        base_url: "",
        provider: "",
      });
    } finally {
      if (!controller.signal.aborted) setTesting(false);
    }
  }, [probe]);

  useEffect(() => () => abort.current?.abort(), []);

  return (
    <div className="flex items-center gap-2.5">
      <button
        type="button"
        onClick={run}
        disabled={testing}
        className="rounded-md border-0 bg-transparent px-2.5 py-1.5 font-mono text-[11px] text-text-muted shadow-border transition-colors hover:text-primary disabled:opacity-40"
        title="Send one real completion and check that content comes back"
      >
        {testing ? "testing…" : "test connection"}
      </button>
      {result && (
        <span
          className="font-mono text-[10.5px]"
          style={{ color: result.ok ? "var(--color-primary)" : "var(--color-secondary)" }}
        >
          {result.ok ? result.summary : result.reason}
        </span>
      )}
    </div>
  );
}
