#!/usr/bin/env python3
"""Report which model each relay alias actually resolves to, right now.

**An alias is not a model.** `skynet` is a relay endpoint name, and over the life
of this project it has been repointed at Gemma 4 31B, then
`Ornith-1.5-35B-A3B-W4A16-SYM`, then `qwen38-27B-v2` — three different
architectures, parameter counts and quantisation schemes — with nothing in the
record noticing until 2026-08-24 (`OPEN_QUESTIONS.md` Q12). Every figure produced
through an alias is dated evidence about whatever was behind it that day, and a
manifest that records the alias has recorded nothing.

`GET /v1/models` is not sufficient: the relay answers `skynet` with
`upstream_model: "auto"` because it hot-swaps. The only reliable identification
is to issue a completion and read the `model` field off the *response* envelope,
which names the weights that actually served it. That is what this does.

Usage:

    uv run python scripts/model_identity.py                  # every alias the relay lists
    uv run python scripts/model_identity.py skynet           # just one
    uv run python scripts/model_identity.py --json           # for a manifest

The `--json` form emits the `model:` string an experiment manifest should carry,
in the `relay/<served-model>@<date>` shape `EXP-2026-08-018` established. Pass
`--date` to stamp it; the script will not invent one, because a wrong date on a
model identity is worse than an absent one.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

#: The relay this project uses. It was ``:4000`` until 2026-09-11, when probing
#: that port reported ``skynet`` healthy while the pipeline's own endpoint,
#: ``:9090``, returned HTTP 404 for it — so the provenance tool was describing a
#: relay nothing in the pipeline talks to. Operator directive: only ``:9090``
#: with ``default-model``.
DEFAULT_BASE_URL = "http://localhost:9090/v1"

#: Aliases worth probing by default even if the relay does not list them. These
#: are the three roles a model plays in this project — answer path, grader, bank
#: author — and they can be pointed at different endpoints.
#: Aliases worth probing when none is named. ``default-model`` first, because
#: it is the one every figure in this project now comes through; the others are
#: kept so a relay that still exposes them is still described.
INTERESTING = ("default-model", "auto", "skynet", "local")


def _base_url() -> str:
    for var in ("SYNTHESIS_LLM_BASE_URL", "PLANNER_LLM_BASE_URL", "SPECIALIST_LLM_BASE_URL"):
        value = os.environ.get(var, "").strip()
        if value:
            return value.rstrip("/")
    return DEFAULT_BASE_URL


def _post(url: str, payload: dict, timeout: float) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _get(url: str, timeout: float) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.load(response)


def list_aliases(base_url: str, timeout: float) -> list[dict]:
    """What the relay says it offers. Advertised, not verified."""
    try:
        return _get(f"{base_url}/models", timeout).get("data", [])
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"could not list models at {base_url}: {exc}", file=sys.stderr)
        return []


def resolve(base_url: str, alias: str, timeout: float) -> dict:
    """Identify the weights behind ``alias`` from a response envelope.

    ``max_tokens`` is deliberately tiny: the envelope names the model whether or
    not the completion has any content, and this repository's local relay serves
    a reasoning model that truncates to empty below roughly 2048 tokens
    (`memory: skynet reasoning budget`). An empty `choices[0]` is expected here
    and is not a failure.
    """
    payload = {
        "model": alias,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 16,
    }
    try:
        body = _post(f"{base_url}/chat/completions", payload, timeout)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"alias": alias, "served_model": None, "error": str(exc)}
    return {
        "alias": alias,
        "served_model": body.get("model"),
        "system_fingerprint": body.get("system_fingerprint"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("aliases", nargs="*", help="aliases to probe (default: every alias the relay lists)")
    parser.add_argument("--base-url", default=None, help=f"OpenAI-compatible base URL (default: env, else {DEFAULT_BASE_URL})")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--json", action="store_true", help="emit JSON, including a manifest-ready model string")
    parser.add_argument("--date", default=None, help="date to stamp into the manifest string (YYYY-MM-DD). Not invented if absent")
    args = parser.parse_args()

    base_url = args.base_url or _base_url()
    advertised = list_aliases(base_url, args.timeout)
    advertised_by_id = {entry.get("id"): entry for entry in advertised}

    targets = args.aliases or [a for a in advertised_by_id if a in INTERESTING] or list(advertised_by_id)
    if not targets:
        print("no aliases to probe", file=sys.stderr)
        return 1

    results = []
    for alias in targets:
        row = resolve(base_url, alias, args.timeout)
        advertised_upstream = (advertised_by_id.get(alias, {}).get("relay") or {}).get("upstream_model")
        row["advertised_upstream"] = advertised_upstream
        # The whole point: what the relay advertises and what it serves can
        # differ, and the difference is exactly the failure mode Q12 recorded.
        row["advertisement_matches_reality"] = (
            None if row["served_model"] is None or advertised_upstream is None
            else advertised_upstream == row["served_model"]
        )
        if args.date and row["served_model"]:
            row["manifest_model"] = f"relay/{row['served_model']}@{args.date}"
        results.append(row)

    if args.json:
        print(json.dumps({"base_url": base_url, "resolved": results}, indent=2))
        return 0

    print(f"relay: {base_url}\n")
    width = max(len(r["alias"]) for r in results)
    for row in results:
        served = row["served_model"] or f"UNREACHABLE ({row.get('error', '')[:60]})"
        line = f"  {row['alias']:<{width}}  ->  {served}"
        if row["advertisement_matches_reality"] is False:
            line += f"   [relay advertises {row['advertised_upstream']!r}]"
        print(line)
    print(
        "\nRecord the served model, not the alias. Manifest form:"
        "\n  model: \"relay/<served-model>@<YYYY-MM-DD>\""
        "\nRerun with --date YYYY-MM-DD --json to get that string directly."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
