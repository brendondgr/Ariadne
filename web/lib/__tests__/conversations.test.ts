import { afterEach, describe, expect, it, vi } from "vitest";
import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  renameConversation,
} from "../conversations";
import type { ConversationDetailDTO, ConversationSummaryDTO } from "../types";

function jsonResponse(body: unknown, ok = true, status = 200): Response {
  return {
    ok,
    status,
    statusText: ok ? "OK" : "Error",
    json: async () => body,
  } as Response;
}

/** A `fetch`-shaped mock so `mock.calls` types as `[string, RequestInit][]`
 *  without needing a cast at each call site. */
function mockFetch(response: Response) {
  return vi.fn(async (...args: [string, RequestInit?]) => {
    void args;
    return response;
  });
}

const SUMMARY: ConversationSummaryDTO = {
  id: "c-1",
  title: "New conversation",
  created_at: "2026-07-08T10:00:00+00:00",
  updated_at: "2026-07-08T10:00:00+00:00",
  turn_count: 0,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("conversations client", () => {
  it("listConversations GETs /api/conversations and unwraps the conversations array", async () => {
    const fetchMock = mockFetch(jsonResponse({ conversations: [SUMMARY] }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await listConversations();

    expect(result).toEqual([SUMMARY]);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/conversations");
    expect(init?.method ?? "GET").toBe("GET");
  });

  it("createConversation POSTs a title body and returns the created summary", async () => {
    const fetchMock = mockFetch(jsonResponse(SUMMARY));
    vi.stubGlobal("fetch", fetchMock);

    const result = await createConversation("My thread");

    expect(result).toEqual(SUMMARY);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/conversations");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toEqual({ title: "My thread" });
  });

  it("getConversation GETs the detail endpoint with the encoded id and returns turns", async () => {
    const detail: ConversationDetailDTO = {
      ...SUMMARY,
      id: "c 1/with-special",
      turns: [
        {
          id: "t-1",
          conversation_id: "c 1/with-special",
          seq: 0,
          role: "user",
          created_at: "2026-07-08T10:00:00+00:00",
          question: "What mitigates T1047?",
          payload: null,
          mode: "query",
          drafter: "llm",
          route: null,
        },
      ],
    };
    const fetchMock = mockFetch(jsonResponse(detail));
    vi.stubGlobal("fetch", fetchMock);

    const result = await getConversation("c 1/with-special");

    expect(result).toEqual(detail);
    const [url] = fetchMock.mock.calls[0];
    expect(url).toBe(`/api/conversations/${encodeURIComponent("c 1/with-special")}`);
  });

  it("renameConversation PATCHes the title", async () => {
    const renamed = { ...SUMMARY, title: "Renamed" };
    const fetchMock = mockFetch(jsonResponse(renamed));
    vi.stubGlobal("fetch", fetchMock);

    const result = await renameConversation("c-1", "Renamed");

    expect(result).toEqual(renamed);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/conversations/c-1");
    expect(init?.method).toBe("PATCH");
    expect(JSON.parse(init?.body as string)).toEqual({ title: "Renamed" });
  });

  it("deleteConversation DELETEs and returns { deleted: true }", async () => {
    const fetchMock = mockFetch(jsonResponse({ deleted: true }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await deleteConversation("c-1");

    expect(result).toEqual({ deleted: true });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/conversations/c-1");
    expect(init?.method).toBe("DELETE");
  });

  it("throws a descriptive error on a non-ok response (404 conversation not found)", async () => {
    const fetchMock = mockFetch(jsonResponse({ detail: "Conversation not found" }, false, 404));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getConversation("missing")).rejects.toThrow(/404/);
  });
});
