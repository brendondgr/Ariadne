# RESULTS — <EXP-ID> <title>  *(negative / abandoned)*

> Use this in place of `RESULTS.md` when an experiment failed, was abandoned, or
> returned a null result. Set `status: failed` (it broke) or `superseded` (it was
> replaced) in the manifest. **Never delete the directory.** A deleted dead end
> is a dead end you walk into twice.

## 1. Headline

What was tried and what happened. Two sentences, no hedging.

## 2. Why it failed

The mechanism, as far as it is understood. Distinguish clearly between:

- **It broke** — an implementation or infrastructure fault. Fixable.
- **It did not work** — the idea was tested fairly and the effect was not there. A real finding.
- **We stopped** — ran out of time, compute, or interest. Not evidence of anything.

Conflating these three is how a repository loses the difference between a bug
and a null result.

## 3. What was ruled out

The useful part. What does this tell the next person not to try, and how
confident should they be? If it rules out nothing, say so.

## 4. Salvage

Anything reusable — code, data, a harness, a partial measurement. Point at it.

## 5. Paper implication

Usually a limitations-section line, sometimes a related-work line. Occasionally
this is the paper. Say which.
