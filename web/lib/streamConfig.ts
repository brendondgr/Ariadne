/**
 * Client-side resilience thresholds for the pipeline SSE streams.
 *
 * The backend runs synthesis (`compose → verify → narrate`) silently — no
 * events flow between `status:{phase:"answering"}` and the terminal
 * `answer`/`done`. If that phase (or any node) hangs, the socket simply goes
 * quiet with no terminal frame, so the reader would block forever. These
 * thresholds let the client notice the silence and turn it into a visible
 * state instead of an endless spinner.
 */

function envMs(name: string, fallback: number): number {
  const raw = process.env[name];
  if (!raw) return fallback;
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

/**
 * Hard inactivity budget: if no bytes arrive on an SSE stream for this long,
 * treat it as stalled and fail the run with a visible error. 90s comfortably
 * exceeds worst-case legitimate synthesis (the narrator's own HTTP timeout is
 * ~30s, after which it falls back deterministically) while still catching a
 * true hang in seconds rather than hours.
 */
export const SSE_STALL_MS = envMs("NEXT_PUBLIC_SSE_STALL_MS", 90_000);

/**
 * Soft threshold: once a turn has been composing this long, the UI escalates
 * from "Composing the answer" to a "taking longer than usual" note so the
 * analyst always knows the run is still alive and being watched.
 */
export const SSE_SLOW_MS = envMs("NEXT_PUBLIC_SSE_SLOW_MS", 25_000);
