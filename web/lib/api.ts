/**
 * Typed client for the Ariadne FastAPI service.
 *
 * Requests are same-origin (`/api/*`): `next.config.ts` rewrites that prefix to
 * the FastAPI process, so no CORS or absolute URLs are needed. Set
 * `NEXT_PUBLIC_API_BASE` only to point the browser at a non-proxied host.
 */

import type {
  AdminActionBody,
  AdminEvent,
  ApiConfig,
  ApiConfigUpdate,
  ApiHealth,
  GraphDataset,
  GraphPayload,
  QueryEvent,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

function url(path: string): string {
  return `${API_BASE}${path}`;
}

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url(path), { ...init, headers: { Accept: "application/json", ...init?.headers } });
  if (!res.ok) {
    throw new Error(`${init?.method ?? "GET"} ${path} failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export function getHealth(signal?: AbortSignal): Promise<ApiHealth> {
  return getJson<ApiHealth>("/api/health", { signal });
}

export function getConfig(signal?: AbortSignal): Promise<ApiConfig> {
  return getJson<ApiConfig>("/api/config", { signal });
}

export function getGraph(dataset: GraphDataset, signal?: AbortSignal): Promise<GraphPayload> {
  return getJson<GraphPayload>(`/api/graph/${dataset}`, { signal });
}

export function putConfig(update: ApiConfigUpdate, signal?: AbortSignal): Promise<ApiConfig> {
  return getJson<ApiConfig>("/api/config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
    signal,
  });
}

export interface QueryRequestBody {
  question: string;
  mode: "plan" | "query";
  drafter: "deterministic" | "llm";
}

/** Parse one raw SSE frame (`event:`/`data:` lines) into `{ type, data }`. */
export function parseSseFrame(frame: string): { type: string; data: unknown } | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (!dataLines.length) return null;
  try {
    return { type: event, data: JSON.parse(dataLines.join("\n")) };
  } catch {
    return null;
  }
}

/** POST `body` to `path` and invoke `onFrame` for each parsed SSE frame. */
async function postSseStream(
  path: string,
  body: unknown,
  onFrame: (frame: { type: string; data: unknown }) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(url(path), {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`POST ${path} failed: ${res.status} ${res.statusText}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      // SSE frames are delimited by a blank line.
      let sep: number;
      while ((sep = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        const parsed = parseSseFrame(frame);
        if (parsed) onFrame(parsed);
      }
    }
    const tail = parseSseFrame(buffer);
    if (tail) onFrame(tail);
  } finally {
    reader.releaseLock();
  }
}

/**
 * POST a question and stream the pipeline's Server-Sent Events, invoking
 * `onEvent` for each parsed frame. Resolves when the stream closes; pass an
 * `AbortSignal` to cancel an in-flight run.
 */
export function streamQuery(
  body: QueryRequestBody,
  onEvent: (event: QueryEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return postSseStream("/api/query", body, (frame) => onEvent(frame as QueryEvent), signal);
}

/** Run an admin (infra/data/graph) action, streaming its log + done events. */
export function streamAdmin(
  body: AdminActionBody,
  onEvent: (event: AdminEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return postSseStream("/api/admin", body, (frame) => onEvent(frame as AdminEvent), signal);
}
