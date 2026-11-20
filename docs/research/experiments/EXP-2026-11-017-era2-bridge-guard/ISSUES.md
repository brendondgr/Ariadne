# ISSUES — EXP-2026-11-017

Bugs, anomalies, aborted runs, and gotchas. Also the honest record of anything
the manifest could not capture: unrecorded seeds, an unknown commit, a dirty
tree at run time. An empty file is fine; a missing one is not.

<!-- Entry template — newest first:

## YYYY-MM-DD — <one-line summary>
**Impact:** what this changes about the reported numbers (e.g. "seed 3 excluded; n=4 not 5 for this cell").
**Cause:** the mechanism, if known.
**Resolution:** what was done. "Not resolved" is a valid answer.
**Paper implication:** what must be stated in the paper because of this.

-->

## 2026-11-19 — the :9090 tunnel dropped at 21:15:02; T-full (variants) and the three Qwen dev arms ran in a second sitting

**Impact:**
- **Two sittings, one commit (39b79c30), checked again in `logs/TREE2`.**
  - **Sitting 1, 17:27–21:15:** R, and E, T-lazy and T-lazy-G on the variants, plus Gemma dev.
  - **Sitting 2:** dev E, dev T-lazy and dev T-full, then T-full on the variants.
- **E (variants) and dev E come from different sittings.** Their figures are paired with the
  typed arms of their own set, so each comparison stays within one tree.
- **Every planner arm that is scored passed H1.**

**Cause:**
- **T-full attempt 1 on the variants had 29 model-less answers.** 23 were relay errors ("stream
  ended prematurely", or "could not reach localhost:9090") and 6 were empty model replies.
- **H1 moved that output to `logs/dropped-var-T-full.1.json`,** and `run.sh` re-ran the arm.
- **The re-run and all three dev arms started inside the tunnel's 20 s restart window**
  (systemd restarted it at 21:15:22). Each failed on its first call with "connection refused"
  and ran no question.

**Resolution:**
- **`logs/resume.sh` re-ran the four arms on the same commit,** after re-verifying the stores.
  It waits for the relay to answer before each arm.
- **The failed starts ran no question, so they are not counted as H1's one allowed re-run.**
  T-full's next attempt is numbered 3.
- **The committed `run.sh` has no relay wait.** The next run script needs one: retry only once
  `localhost:9090/v1/models` answers.

**Paper implication:** none. This is an engineering run.
