"use client";

import { useEffect, useState } from "react";
import type { ApiLlmHealth, LiveSource } from "@/lib/types";
import { getHealth } from "@/lib/api";
import { InfraStatusPill } from "./InfraStatusPill";

/**
 * Polls `GET /api/health` so the header pills reflect the *real* Neo4j/Gremlin
 * reachability, independent of any in-flight query. Falls back to the provided
 * sources for the first paint, then refreshes on an interval.
 */
export function InfraStatusBar({ fallback }: { fallback: LiveSource[] }) {
  const [sources, setSources] = useState<LiveSource[]>(fallback);
  const [llm, setLlm] = useState<ApiLlmHealth | null>(null);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();

    const poll = async () => {
      try {
        const health = await getHealth(controller.signal);
        if (!active) return;
        setSources(
          health.sources.map((s) => ({
            backend: s.backend,
            status: s.status,
            nodes: s.nodes ?? undefined,
            reason: s.reason ?? undefined,
          })),
        );
        setLlm(health.llm ?? null);
      } catch {
        // Keep the last-known status if a poll fails (backend restart, etc.).
      }
    };

    void poll();
    const id = window.setInterval(poll, 5000);
    return () => {
      active = false;
      controller.abort();
      window.clearInterval(id);
    };
  }, []);

  return (
    <>
      {sources.map((source) => (
        <InfraStatusPill key={source.backend} source={source} />
      ))}
      {llm && (
        <InfraStatusPill
          source={{
            backend: "llm",
            status: llm.status,
            reason:
              llm.reason ??
              (llm.enabled ? `${llm.model} · reachable` : `${llm.model} · endpoint reachable (LLM drafter off by default)`),
          }}
        />
      )}
    </>
  );
}
