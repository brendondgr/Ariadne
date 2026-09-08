#!/usr/bin/env python3
"""A content-addressed cache for the rewrite stage's model choices.

A model seam makes an evaluation expensive and, worse, makes a re-run a
*different* run. Q2 has been open since 2026-08 precisely because no
LLM-in-the-loop arm has ever been run twice. This cache is what makes running one
twice cheap: the second run reads what the first one chose, so a downstream
change can be attributed to the pipeline rather than to the model having a
different afternoon.

**The key is the whole design.** ``sha256(prompt_version, served_model,
question)``:

``prompt_version``  a prompt change is a different experiment, so it must not
                    silently reuse the old run's picks.
``served_model``    the *weights that answered*, read off a response envelope,
                    never the alias. `skynet` has pointed at three different
                    architectures over this project's life and nothing noticed
                    for weeks (D-028). An alias in this key would let one model's
                    choices be served as another's.
``question``        the analyst's words, verbatim. Not the form, not a
                    normalisation of the text: two questions that normalise the
                    same are still two questions, and the stage's whole subject
                    is what different phrasings do.

Entries are plain JSON files, one per key, so a run's cache can be committed
beside the experiment and read by a human.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("ariadne.planner.rewrite.cache")

#: Default root when nothing is configured. Git-ignored: a workbench session's
#: picks are not a research artifact. An experiment points
#: ``ARIADNE_REWRITE_CACHE_DIR`` at its own ``data/cache/`` instead.
DEFAULT_ROOT = Path("data") / "cache" / "rewrite"


def cache_key(prompt_version: str, served_model: str, question: str) -> str:
    """The content address for one (prompt, weights, question) triple."""
    digest = hashlib.sha256()
    for part in (prompt_version, served_model, question):
        # Length-prefixed so ("ab", "c") and ("a", "bc") cannot collide.
        blob = (part or "").encode()
        digest.update(str(len(blob)).encode())
        digest.update(b"\0")
        digest.update(blob)
    return digest.hexdigest()


@dataclass(frozen=True)
class CacheEntry:
    """What one cached call recorded, and enough context to audit it."""

    key: str
    prompt_version: str
    served_model: str
    question: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "prompt_version": self.prompt_version,
            "served_model": self.served_model,
            "question": self.question,
            "payload": self.payload,
        }


class RewriteCache:
    """A directory of JSON entries. Read-through; misses are not errors.

    Every failure mode here is a miss, never an exception. A cache that can take
    a run down is worse than no cache, and a corrupt entry is a reason to ask the
    model again rather than to stop.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        configured = root or os.environ.get("ARIADNE_REWRITE_CACHE_DIR") or DEFAULT_ROOT
        self.root = Path(configured)

    def path_for(self, key: str) -> Path:
        # One level of fan-out: a bank run puts ~600 files in a directory and a
        # sweep puts several thousand.
        return self.root / key[:2] / f"{key}.json"

    def get(self, key: str) -> CacheEntry | None:
        path = self.path_for(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            logger.warning("unreadable rewrite cache entry %s: %s", path, exc)
            return None
        if not isinstance(data, dict) or "payload" not in data:
            logger.warning("malformed rewrite cache entry %s", path)
            return None
        return CacheEntry(
            key=str(data.get("key") or key),
            prompt_version=str(data.get("prompt_version") or ""),
            served_model=str(data.get("served_model") or ""),
            question=str(data.get("question") or ""),
            payload=data.get("payload") or {},
        )

    def put(self, entry: CacheEntry) -> None:
        path = self.path_for(entry.key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Written through a temporary file in the same directory and renamed,
            # so a run interrupted mid-write leaves no half-entry for the next
            # run to read as an answer.
            with tempfile.NamedTemporaryFile(
                "w", dir=path.parent, delete=False, encoding="utf-8"
            ) as handle:
                json.dump(entry.to_dict(), handle, indent=2, sort_keys=True)
                handle.write("\n")
                temp = Path(handle.name)
            temp.replace(path)
        except OSError as exc:
            logger.warning("could not write rewrite cache entry %s: %s", path, exc)
