#!/usr/bin/env python3
"""Optional embedding reranker over the shipped name index's candidates (EXP-2026-09-028).

The BM25 name index finds the right entity for a paraphrased or described
question most of the time — top-25 recall 0.86 at T4 and 0.94 at T5 on the
exposed bank — but ranks it first only 0.31 / 0.53 of the time, and a closed
choice reads the top five. Re-ordering those 25 by embedding similarity moved
T4 rank-1 to 0.52 in the 2026-09-15 probe. That is the whole job here: a
**re-ordering of a list the index already produced**, never a new candidate,
never an acceptance decision, never a threshold.

Three rules keep it honest:

* it stands down when an exact complete name is in the question — the caller
  checks that, because an exact name is a lookup and the probe showed the
  reranker *hurting* T3 (0.96 → 0.69) when let loose on it;
* it is off by default (``ARIADNE_RERANK``) and a missing backend is not an
  error: the list is returned unchanged and the fact recorded, so the pipeline
  never depends on a model file being present;
* the backend is an adapter. In-process ``fastembed`` when importable; else
  the evaluation venv's interpreter over a pipe when it exists (the weights are
  already cached there); else nothing. Versioned by model name.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Sequence

from .namesearch import Candidate, description_of

MODEL = "BAAI/bge-small-en-v1.5"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
_EVAL_VENV = Path.home() / ".cache" / "mycelium-eval-venv" / "bin" / "python"

_EMBED_SCRIPT = r"""
import json, sys
import numpy as np
from fastembed import TextEmbedding
payload = json.load(sys.stdin)
model = TextEmbedding(payload["model"])
vecs = np.array(list(model.embed(payload["texts"])))
vecs = vecs / np.linalg.norm(vecs, axis=1, keepdims=True)
json.dump(vecs.tolist(), sys.stdout)
"""


def rerank_on() -> bool:
    return os.environ.get("ARIADNE_RERANK", "").strip().lower() in {"1", "true", "yes", "on"}


def pool_size() -> int:
    try:
        return max(5, int(os.environ.get("ARIADNE_RERANK_POOL", "25")))
    except ValueError:
        return 25


@lru_cache(maxsize=1)
def backend() -> str:
    """``"fastembed"``, ``"venv"`` or ``""`` — decided once per process."""
    try:
        import fastembed  # noqa: F401

        return "fastembed"
    except Exception:  # noqa: BLE001 — absent or broken, either way not in-process
        pass
    if _EVAL_VENV.exists():
        return "venv"
    return ""


def _embed(texts: Sequence[str]) -> list[list[float]] | None:
    kind = backend()
    if kind == "fastembed":
        import numpy as np
        from fastembed import TextEmbedding

        vecs = np.array(list(_model().embed(list(texts))))
        vecs = vecs / np.linalg.norm(vecs, axis=1, keepdims=True)
        return vecs.tolist()
    if kind == "venv":
        try:
            proc = subprocess.run(
                [str(_EVAL_VENV), "-c", _EMBED_SCRIPT],
                input=json.dumps({"model": MODEL, "texts": list(texts)}),
                capture_output=True, text=True, timeout=120, check=True,
                env={**os.environ, "HF_HUB_OFFLINE": "1"},
            )
            return json.loads(proc.stdout)
        except Exception:  # noqa: BLE001 — a failed bridge is "no reranker", recorded by the caller
            return None
    return None


@lru_cache(maxsize=1)
def _model():
    from fastembed import TextEmbedding

    return TextEmbedding(MODEL)


def rerank(question: str, candidates: Iterable[Candidate], *, dataset: str) -> tuple[list[Candidate], str]:
    """Re-order ``candidates`` by embedding similarity to ``question``.

    Returns ``(ordered, backend_used)``; ``backend_used`` is ``""`` when the
    list came back unchanged because no backend could run, so the answer record
    can say which it was.
    """
    cands = list(candidates)
    if len(cands) < 2:
        return cands, ""
    docs = [f"{c.name}. {description_of(dataset, c.entity_id)}".strip() for c in cands]
    vecs = _embed([QUERY_PREFIX + (question or ""), *docs])
    if not vecs:
        return cands, ""
    q, rest = vecs[0], vecs[1:]
    sims = [sum(a * b for a, b in zip(q, d)) for d in rest]
    order = sorted(range(len(cands)), key=lambda i: (-sims[i], cands[i].entity_id))
    return [Candidate(cands[i].entity_id, cands[i].label, cands[i].name, round(sims[i], 4)) for i in order], backend()
