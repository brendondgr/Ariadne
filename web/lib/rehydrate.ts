/**
 * Stored-turn rehydration: turn a persisted user+assistant turn pair (as
 * `GET /api/conversations/{id}` returns them) into the same `WorkbenchRun`
 * shape the live stream produces.
 *
 * Reuses `applyConversationEvent` (the same reducer `submit()` folds live SSE
 * frames through in `runMachine.ts`) so a rehydrated turn and a freshly
 * streamed turn are built by identical logic — the only difference is where
 * the events come from (`payload.events` vs. the wire).
 */

import { applyConversationEvent, emptyAccumulator, runInputsFromAccumulator } from "./runMachine";
import { buildRun } from "./adapt";
import type { QueryEvent, StoredTurn, WorkbenchRun } from "./types";

/**
 * Build a `WorkbenchRun` for one conversational turn from its stored user +
 * assistant rows. `assistantTurn` is null for a user turn with no recorded
 * reply yet (defensive — the backend always persists the pair together).
 */
export function buildRunFromStoredTurn(
  userTurn: StoredTurn,
  assistantTurn: StoredTurn | null,
): WorkbenchRun {
  const question = userTurn.question ?? "";
  const mode = userTurn.mode ?? assistantTurn?.mode ?? "query";
  const drafter = userTurn.drafter ?? assistantTurn?.drafter ?? "deterministic";

  const acc = emptyAccumulator(question, mode, drafter);
  const payload = assistantTurn?.payload ?? null;

  if (payload) {
    // Replay the exact transformed SSE events the backend captured for this
    // turn through the SAME reducer live streaming uses — this alone populates
    // acc.reply/route/validation/plan/evidence/answer/etc. when the `final`/
    // `route`/`validation` events are present in the replayed log (they always
    // are; `events` is the literal frame log minus the raw `conversation` frame).
    for (const evt of payload.events) {
      applyConversationEvent(acc, evt as QueryEvent, 0);
    }
    // The persisted top-level fields are the source of truth — fall back to
    // them for anything the replayed events didn't set (defensive; e.g. an
    // older stored payload predating a given event type).
    if (!acc.reply) {
      acc.reply = {
        text: payload.final_answer,
        route: payload.route,
        composer: drafter,
        grounded: payload.route === "graph",
      };
    }
    acc.route = acc.route ?? payload.route;
    acc.validation = acc.validation ?? payload.validation;
    acc.status = (payload.status as WorkbenchRun["status"]) || acc.status;
    if (typeof payload.exit_code === "number") acc.exitCode = payload.exit_code as WorkbenchRun["exitCode"];
  } else {
    acc.status = "idle";
  }

  const createdAtMs = Date.parse(assistantTurn?.created_at ?? userTurn.created_at ?? "");
  const inputs = runInputsFromAccumulator(userTurn.id, acc, {
    createdAt: Number.isFinite(createdAtMs) ? createdAtMs : 0,
    elapsedMs: 0,
  });
  return buildRun(inputs);
}
