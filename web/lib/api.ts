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
  ApiLlmEndpointProbe,
  ApiLlmTestResult,
  ApiModelList,
  EvaluationReport,
  EvalRunEvent,
  GraphDataset,
  GraphPayload,
  QueryEvent,
} from "./types";
import { SSE_STALL_MS } from "./streamConfig";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

/**
 * Thrown when an SSE stream goes silent past the inactivity budget — no bytes
 * for `idleMs` with no terminal event. Distinct type so the run machine can
 * tell a genuine stall apart from a network failure or a user-initiated abort.
 */
export class SseStallError extends Error {
  readonly idleMs: number;
  constructor(idleMs: number) {
    super(
      `The response stalled — no update from the server for ${Math.round(
        idleMs / 1000,
      )}s. The query may still be running on the server, or a step may be stuck. Try again.`,
    );
    this.name = "SseStallError";
    this.idleMs = idleMs;
  }
}

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

export function getEvaluation(signal?: AbortSignal): Promise<EvaluationReport> {
  return getJson<EvaluationReport>("/api/evaluation", { signal });
}

/**
 * Ask an endpoint what models it serves.
 *
 * POST, not GET: the body may carry an unsaved endpoint and an API key, and a
 * secret has no business in a query string. Never rejects on an unreachable
 * server — that comes back as `ok: false` with a reason, because someone's GPU
 * box being off is a normal state rather than an error to shout about.
 */
export function getLlmModels(
  probe: ApiLlmEndpointProbe,
  signal?: AbortSignal,
): Promise<ApiModelList> {
  return getJson<ApiModelList>("/api/llm/models", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(probe),
    signal,
  });
}

/**
 * Prove an endpoint answers, by having the server send a real completion.
 *
 * Deliberately stronger than reachability: a TCP check and a model listing both
 * pass against a server that cannot complete anything.
 */
export function testLlm(
  probe: ApiLlmEndpointProbe,
  signal?: AbortSignal,
): Promise<ApiLlmTestResult> {
  return getJson<ApiLlmTestResult>("/api/llm/test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(probe),
    signal,
  });
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
  /** Rewrite the prose with a model, over claims already composed and verified.
   *  Deliberately separate from `drafter`: `drafter: "llm"` also hands QUERY
   *  construction to a model, which scores 0.5000 against the template
   *  cascade's 0.9467 on the same unseen questions. The narrator seam is the one
   *  measured not to change a fact — 284/284 claims byte-identical, +0.0000
   *  coverage — and it costs ~1,340x the deterministic composer, so it is
   *  opt-in per question. */
  narrate?: boolean;
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

/**
 * POST `body` to `path` and invoke `onFrame` for each parsed SSE frame.
 *
 * Guards against a silently stalled stream: each `reader.read()` races an
 * inactivity timer (reset on every chunk). If no bytes arrive within
 * `stallMs`, the reader is cancelled and an {@link SseStallError} is thrown,
 * so a hung backend surfaces as a real error instead of an endless spinner.
 * Pass `stallMs <= 0` to disable the watchdog.
 */
async function postSseStream(
  path: string,
  body: unknown,
  onFrame: (frame: { type: string; data: unknown }) => void,
  signal?: AbortSignal,
  stallMs: number = SSE_STALL_MS,
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
      const { value, done } = await readWithStall(reader, stallMs);
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
  } catch (err) {
    // Cancel so the fetch body / socket is released; the pending read settles.
    await reader.cancel(err).catch(() => {});
    throw err;
  } finally {
    // `cancel()` (above, or on normal completion) releases the lock; guard the
    // no-error path where the reader is still locked.
    try {
      reader.releaseLock();
    } catch {
      // already released by cancel()
    }
  }
}

/**
 * Await the next chunk, but reject with {@link SseStallError} if it doesn't
 * arrive within `stallMs`. `stallMs <= 0` disables the timeout.
 */
function readWithStall(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  stallMs: number,
): Promise<ReadableStreamReadResult<Uint8Array>> {
  const read = reader.read();
  if (stallMs <= 0) return read;
  let timer: ReturnType<typeof setTimeout>;
  const stall = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new SseStallError(stallMs)), stallMs);
  });
  return Promise.race([read, stall]).finally(() => clearTimeout(timer));
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

export interface ConversationQueryBody {
  question: string;
  conversation_id: string;
  mode: "plan" | "query";
  drafter: "deterministic" | "llm";
}

/**
 * POST a question to the memory-inclusive conversation pipeline and stream its
 * Server-Sent Events. Same event shapes as {@link streamQuery} plus the
 * conversation-native `context`/`route`/`validation`/`final`/`conversation`
 * events (see `QueryEvent` in `./types`).
 */
export function streamConversation(
  body: ConversationQueryBody,
  onEvent: (event: QueryEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return postSseStream("/api/conversation-query", body, (frame) => onEvent(frame as QueryEvent), signal);
}

export interface EvalRunBody {
  live: boolean;
  judge: boolean;
  limit?: number;
}

/** Re-run the end-to-end evaluation live, streaming its progress + done event. */
export function streamEvalRun(
  body: EvalRunBody,
  onEvent: (event: EvalRunEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return postSseStream("/api/eval-run", body, (frame) => onEvent(frame as EvalRunEvent), signal);
}
