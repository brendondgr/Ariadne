#!/usr/bin/env python3
"""Re-run kill test T1 for one more relay alias, without touching the recorded run.

    uv run python scripts/killtests_t1_model.py default-model-2           # wait, then run
    uv run python scripts/killtests_t1_model.py default-model --no-wait

T1 is provisional until it has run on two or more models (EXP-2026-11-003). This
script adds one model at a time:

1. Waits (polling every 60 s) until the relay reports the alias healthy.
2. Identifies the served weights from a completion's response envelope. **An alias
   is not a model**, so the output folder is named after the served model, never
   the alias.
3. Copies the recorded run's ``t1/gold`` stage, so every model answers exactly the
   same 200 questions, then runs generate -> execute -> score into
   ``logs/killtests-2026-11/t1-models/<served-model>/``.
4. Writes ``killrule.json`` there with the same per-model rule as ``analysis.t1``.

It never writes into ``docs/research/experiments/``. Folding the new models into
EXP-2026-11-003's record is a separate, deliberate step.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.config import load_env  # noqa: E402

load_env()

from utils.killtests import analysis, config, heartbeat  # noqa: E402
from utils.killtests.relay import RelayClient  # noqa: E402
from utils.killtests.stages import atomic_write_json  # noqa: E402
from utils.killtests.t1 import run as t1  # noqa: E402

BASE = Path(__file__).resolve().parents[1] / "logs" / "killtests-2026-11"


def _log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def wait_healthy(relay: RelayClient, alias: str, poll: int) -> None:
    while True:
        try:
            if alias in relay.healthy_aliases():
                return
        except Exception as exc:  # noqa: BLE001 - relay may be restarting
            _log(f"relay unreachable: {exc}")
        time.sleep(poll)


def served_model(relay: RelayClient, alias: str, tries: int = 10) -> str:
    """Envelope model name plus the stop token id.

    The envelope ``model`` is the backend's *served-model-name*, which an operator
    can set to anything (on 2026-11-13 Gemma answered as ``default-model-2``). The
    stop token id is a property of the tokenizer: 106 is Gemma's ``<end_of_turn>``,
    151645 is Qwen's ``<|im_end|>``.
    """
    for i in range(tries):
        try:
            req = urllib.request.Request(
                relay.base_url + "/chat/completions",
                data=json.dumps({"model": alias, "max_tokens": 2048,
                                 "messages": [{"role": "user", "content": "Reply with the word ok."}]}).encode(),
                headers={"content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as resp:  # noqa: S310
                env = json.loads(resp.read().decode())
            name = str(env.get("model") or "unknown")
            stop = (env.get("choices") or [{}])[0].get("stop_reason")
            return f"{name}-stop{stop}"
        except Exception as exc:  # noqa: BLE001 - a freshly loaded slot can fail its first calls
            _log(f"probe {i + 1}/{tries} failed: {exc}")
        time.sleep(30)
    raise SystemExit(f"{alias}: healthy but never answered a probe")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("alias")
    ap.add_argument("--no-wait", action="store_true")
    ap.add_argument("--poll", type=int, default=60)
    args = ap.parse_args(argv)

    base_cfg = config.get()
    relay = RelayClient(base_cfg.relay_url, max_tokens=base_cfg.relay_max_tokens)
    if not args.no_wait:
        _log(f"waiting for {args.alias} to report healthy")
        wait_healthy(relay, args.alias, args.poll)
    model = served_model(relay, args.alias)
    _log(f"{args.alias} serves {model}")

    out = BASE / "t1-models" / re.sub(r"[^A-Za-z0-9._-]+", "_", f"{model}__via_{args.alias}")
    hdr = out / "run_header.json"
    if hdr.exists() and json.loads(hdr.read_text()).get("alias") != args.alias:
        raise SystemExit(f"{out} belongs to another alias; refusing to reuse its cached generations")
    (out / "t1").mkdir(parents=True, exist_ok=True)
    for name in ("gold.json", "gold.done"):
        if not (out / "t1" / name).exists():
            shutil.copy2(BASE / "t1" / name, out / "t1" / name)

    os.environ["KILLTESTS_OUT"] = str(out.relative_to(config.REPO))
    os.environ["KILLTESTS_MODELS"] = args.alias
    cfg = config.get()
    heartbeat.configure(out, run=f"t1-{model}")
    atomic_write_json(out / "run_header.json", {"alias": args.alias, "served_model": model,
                                                "started_at": time.time(), "gold_from": str(BASE / "t1")})
    t1.run(cfg, out)
    verdict = {k: v for k, v in analysis.t1(out).items() if k != "metrics"}
    verdict["alias"], verdict["served_model_probe"] = args.alias, model
    atomic_write_json(out / "killrule.json", verdict)
    for m, v in verdict["inputs"].items():
        _log(f"DONE {model}: cypher-3shot {v['cypher_3shot']:.3f}  gremlin-3shot {v['gremlin_3shot']:.3f}  "
             f"killed={v['killed']}  served={verdict.get('served_models')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
