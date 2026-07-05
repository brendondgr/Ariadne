import { describe, expect, it, vi } from "vitest";
import type { AdminActionBody, AdminEvent } from "../types";
import { reducePipelineEvent, runYoloPipeline } from "../pipeline";

describe("reducePipelineEvent", () => {
  it("routes log/status frames to onLine and done to onResult", () => {
    const lines: string[] = [];
    let result: { ok: boolean; message: string } | null = null;
    const handlers = { onLine: (l: string) => lines.push(l), onResult: (r: typeof result) => (result = r) };

    reducePipelineEvent({ type: "log", data: { line: "downloading…", level: "info" } }, handlers);
    reducePipelineEvent({ type: "status", data: { action: "graph-load", message: "loading graphs" } }, handlers);
    reducePipelineEvent({ type: "status", data: { action: "verify" } }, handlers); // no message → falls back to action
    reducePipelineEvent({ type: "done", data: { ok: true, message: "pipeline complete" } }, handlers);

    expect(lines).toEqual(["downloading…", "· loading graphs", "· verify"]);
    expect(result).toEqual({ ok: true, message: "pipeline complete" });
  });
});

describe("runYoloPipeline", () => {
  it("invokes streamAdmin with the yolo-all action and fans events to handlers", async () => {
    const frames: AdminEvent[] = [
      { type: "log", data: { line: "step 1", level: "info" } },
      { type: "done", data: { ok: true, message: "done" } },
    ];
    let sentBody: AdminActionBody | null = null;
    const stream = vi.fn(async (body: AdminActionBody, onEvent: (e: AdminEvent) => void) => {
      sentBody = body;
      frames.forEach(onEvent);
    });

    const lines: string[] = [];
    let result: { ok: boolean; message: string } | null = null;
    await runYoloPipeline(stream, { onLine: (l) => lines.push(l), onResult: (r) => (result = r) });

    expect(sentBody).toEqual({ action: "yolo-all" });
    expect(stream).toHaveBeenCalledOnce();
    expect(lines).toEqual(["step 1"]);
    expect(result).toEqual({ ok: true, message: "done" });
  });

  it("propagates a transport error so the caller can show a failed result", async () => {
    const stream = vi.fn(async () => {
      throw new Error("network down");
    });
    await expect(runYoloPipeline(stream, { onLine: () => {}, onResult: () => {} })).rejects.toThrow(
      "network down",
    );
  });
});
