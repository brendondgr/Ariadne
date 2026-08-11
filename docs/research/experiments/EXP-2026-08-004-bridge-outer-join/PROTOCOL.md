# PROTOCOL — EXP-2026-08-004 <title>

> Write this **before** running anything. A protocol written after the results
> are known is not a protocol. If this experiment is a back-fill of a run that
> already happened, say so in one line here and set `code.commit: unknown` in
> the manifest rather than reconstructing a plan you did not follow.

## Question

What, precisely, are we asking? One or two sentences, phrased so it has an
answer that could come out either way.

## Hypothesis

What we expect and why. If exploratory, write "exploratory — no prior
hypothesis" and do not invent one retrospectively.

## Setup

The system under test, the configuration, and what is held constant. Name the
arm or variant explicitly if this is one cell of a matrix.

## Data

Dataset, version, split, size. Say how examples were selected and whether the
selection could bias the result. Point at the dataset card under
`../../datasets/cards/`.

## Metrics

**Defined, not just named.** For each metric: what it computes, over what
population, and what counts as a success. A metric named but undefined is the
most common way two runs stop being comparable.

## Baselines

What this is compared against, and why that comparison is fair. "No baseline"
is an acceptable answer only if written here explicitly.

## Procedure

The exact commands, in order. Anyone should be able to paste these and get the
same folder back.

```bash
# commands here
```

## What would falsify this

The result that would make us abandon the hypothesis. Write it now, while it is
still cheap to be honest about.
