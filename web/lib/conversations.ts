/**
 * Typed client for the persisted-conversation-thread REST endpoints
 * (`GET/POST /api/conversations`, `GET/PATCH/DELETE /api/conversations/{id}`).
 *
 * Same-origin `/api/*`, mirroring the plain style of `lib/api.ts` (no shared
 * base-URL logic is duplicated here — each function builds its own path since
 * this module is small and intentionally standalone per the frontend spec).
 */

import type { ConversationDetailDTO, ConversationSummaryDTO } from "./types";
import { streamConversation } from "./api";
import type { ConversationQueryBody } from "./api";

// Re-exported so callers can pull the whole conversations surface (CRUD +
// streaming) from one module, per the frontend spec; the implementation lives
// in `./api` alongside `postSseStream`/`streamQuery` to keep that helper reuse
// in one place.
export { streamConversation };
export type { ConversationQueryBody };

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

/** `GET /api/conversations` — list threads, most-recently-updated first. */
export function listConversations(signal?: AbortSignal): Promise<ConversationSummaryDTO[]> {
  return getJson<{ conversations: ConversationSummaryDTO[] }>("/api/conversations", { signal }).then(
    (res) => res.conversations,
  );
}

/** `POST /api/conversations` — create a new (empty) thread. */
export function createConversation(title?: string, signal?: AbortSignal): Promise<ConversationSummaryDTO> {
  return getJson<ConversationSummaryDTO>("/api/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
    signal,
  });
}

/** `GET /api/conversations/{id}` — the thread + all of its turns, for rehydration. */
export function getConversation(id: string, signal?: AbortSignal): Promise<ConversationDetailDTO> {
  return getJson<ConversationDetailDTO>(`/api/conversations/${encodeURIComponent(id)}`, { signal });
}

/** `PATCH /api/conversations/{id}` — rename a thread. */
export function renameConversation(
  id: string,
  title: string,
  signal?: AbortSignal,
): Promise<ConversationSummaryDTO> {
  return getJson<ConversationSummaryDTO>(`/api/conversations/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
    signal,
  });
}

/** `DELETE /api/conversations/{id}` — delete a thread and its turns. */
export function deleteConversation(id: string, signal?: AbortSignal): Promise<{ deleted: true }> {
  return getJson<{ deleted: true }>(`/api/conversations/${encodeURIComponent(id)}`, {
    method: "DELETE",
    signal,
  });
}
