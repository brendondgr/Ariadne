/** Pure wiring for the header "Run Pipeline" button: drive the `--yolo-all`
 *  admin action over SSE and fan its frames out to caller-supplied handlers.
 *  Kept free of React so the event→output contract is unit-testable in node. */
import type { AdminActionBody, AdminEvent } from "@/lib/types";

/** Structural shape of `streamAdmin` — injectable so tests can supply a stub
 *  without pulling the fetch client (and its browser globals) into node. */
export type AdminStreamer = (
  body: AdminActionBody,
  onEvent: (event: AdminEvent) => void,
  signal?: AbortSignal,
) => Promise<void>;

export interface PipelineHandlers {
  /** A streamed log or status line to append to the console. */
  onLine: (line: string) => void;
  /** The terminal result once the pipeline finishes. */
  onResult: (result: { ok: boolean; message: string }) => void;
}

/** Format one admin SSE frame into console output, ignoring frames with no
 *  user-facing text. Exported for direct testing. */
export function reducePipelineEvent(event: AdminEvent, handlers: PipelineHandlers): void {
  if (event.type === "log") handlers.onLine(event.data.line);
  else if (event.type === "status") handlers.onLine(`· ${event.data.message ?? event.data.action}`);
  else if (event.type === "done") handlers.onResult({ ok: event.data.ok, message: event.data.message });
}

/** Run the full `--yolo-all` pipeline, streaming its logs to {@link PipelineHandlers}.
 *  Rejects on transport failure so callers can surface it as a failed result. */
export function runYoloPipeline(
  stream: AdminStreamer,
  handlers: PipelineHandlers,
  signal?: AbortSignal,
): Promise<void> {
  return stream({ action: "yolo-all" }, (event) => reducePipelineEvent(event, handlers), signal);
}
