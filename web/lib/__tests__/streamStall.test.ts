import { afterEach, describe, expect, it, vi } from "vitest";
import { SseStallError, streamConversation, type ConversationQueryBody } from "../api";
import { SSE_STALL_MS } from "../streamConfig";
import type { QueryEvent } from "../types";

const BODY: ConversationQueryBody = {
  question: "q",
  conversation_id: "c-1",
  mode: "query",
  drafter: "llm",
};

const encode = (s: string) => new TextEncoder().encode(s);
const frame = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;

/** A fake stream reader that plays `results` in order, then hangs forever.
 *  `"hang"` yields a never-resolving read to simulate a silent socket. */
type Step = ReadableStreamReadResult<Uint8Array> | "hang";
function fakeReader(results: Step[]) {
  let i = 0;
  return {
    read: () => {
      const r = i < results.length ? results[i++] : "hang";
      if (r === "hang") return new Promise<never>(() => {});
      return Promise.resolve(r);
    },
    cancel: vi.fn(() => Promise.resolve()),
    releaseLock: vi.fn(),
  };
}

function stubFetch(reader: ReturnType<typeof fakeReader>) {
  const fetchMock = vi.fn(async () => ({ ok: true, body: { getReader: () => reader } }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("postSseStream inactivity watchdog", () => {
  it("rejects with SseStallError when the stream is silent past the budget", async () => {
    vi.useFakeTimers();
    const reader = fakeReader([]); // never yields a single byte
    stubFetch(reader);
    const onEvent = vi.fn();

    const settled = streamConversation(BODY, onEvent, undefined).then(
      () => "resolved",
      (e) => e,
    );
    await vi.advanceTimersByTimeAsync(SSE_STALL_MS + 10);
    const result = await settled;

    expect(result).toBeInstanceOf(SseStallError);
    expect((result as SseStallError).idleMs).toBe(SSE_STALL_MS);
    expect(onEvent).not.toHaveBeenCalled();
    expect(reader.cancel).toHaveBeenCalled(); // socket released on stall
  });

  it("resets the timer on each chunk, then stalls once the stream goes quiet", async () => {
    vi.useFakeTimers();
    // One real frame arrives, then the socket goes silent — the watchdog must
    // fire on the post-chunk silence, proving the timer reset per chunk.
    const reader = fakeReader([{ value: encode(frame("status", { phase: "answering" })), done: false }]);
    stubFetch(reader);
    const onEvent = vi.fn();

    const settled = streamConversation(BODY, onEvent, undefined).then(
      () => "resolved",
      (e) => e,
    );
    // Let the first chunk flush, then advance past the budget on the silence.
    await vi.advanceTimersByTimeAsync(1);
    await vi.advanceTimersByTimeAsync(SSE_STALL_MS + 10);
    const result = await settled;

    expect(result).toBeInstanceOf(SseStallError);
    expect(onEvent).toHaveBeenCalledTimes(1);
    expect(onEvent).toHaveBeenCalledWith({ type: "status", data: { phase: "answering" } });
  });

  it("streams a normal run to completion without tripping the watchdog", async () => {
    const reader = fakeReader([
      { value: encode(frame("status", { phase: "answering" })), done: false },
      { value: encode(frame("done", { status: "answered", exit_code: 0 })), done: false },
      { value: undefined as unknown as Uint8Array, done: true },
    ]);
    stubFetch(reader);
    const seen: QueryEvent[] = [];

    await expect(
      streamConversation(BODY, (e) => seen.push(e), undefined),
    ).resolves.toBeUndefined();

    expect(seen).toHaveLength(2);
    expect(seen[0]).toEqual({ type: "status", data: { phase: "answering" } });
    expect(seen[1]).toEqual({ type: "done", data: { status: "answered", exit_code: 0 } });
  });
});
