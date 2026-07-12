#!/usr/bin/env python3
"""Prompt helpers for the setup wizard — stdlib only, matching the repo's UX.

All interactivity funnels through ``WizardUI`` so ``--yes`` mode is one flag
(every prompt resolves to its default) and tests can drive the wizard by
monkeypatching ``input``.
"""

from __future__ import annotations

import getpass

from utils.launcher.display import use_color

_ANSI = {"bold": "\033[1m", "dim": "\033[2m", "reset": "\033[0m"}


class WizardUI:
    """Console interaction for the wizard; ``assume_yes`` makes it silent."""

    def __init__(self, *, assume_yes: bool = False) -> None:
        self.assume_yes = assume_yes
        self._color = use_color()

    # ── output ───────────────────────────────────────────────────────────────

    def _style(self, text: str, style: str) -> str:
        if not self._color:
            return text
        return f"{_ANSI[style]}{text}{_ANSI['reset']}"

    def say(self, message: str) -> None:
        print(f"  {message}", flush=True)

    def header(self, title: str) -> None:
        print(f"\n  {self._style(title, 'bold')}\n", flush=True)

    # ── prompts (every one resolves to its default under --yes) ─────────────

    def confirm(self, question: str, *, default: bool = True) -> bool:
        if self.assume_yes:
            return default
        suffix = "[Y/n]" if default else "[y/N]"
        answer = input(f"  {question} {suffix} ").strip().lower()
        if not answer:
            return default
        return answer in ("y", "yes")

    def prompt_text(self, label: str, default: str, *, secret: bool = False) -> str:
        """Prompt for a value, returning ``default`` when the input is empty."""
        if self.assume_yes:
            return default
        if secret:
            entered = getpass.getpass(f"  {label} [hidden, Enter keeps current]: ")
            return entered if entered else default
        suffix = f" [{default}]" if default else ""
        entered = input(f"  {label}{suffix}: ").strip()
        return entered if entered else default

    def choose(self, question: str, choices: dict[str, str], default: str) -> str:
        """Pick one of ``choices`` (key → description) by its key letter."""
        if self.assume_yes:
            return default
        legend = " / ".join(
            f"[{key}]{label}" if key != default else f"[{key.upper()}]{label}"
            for key, label in choices.items()
        )
        while True:
            answer = input(f"  {question} {legend}: ").strip().lower()
            if not answer:
                return default
            if answer in choices:
                return answer
            self.say(f"Please answer one of: {', '.join(choices)}")

    def failure_menu(
        self, title: str, detail: str, remediation: str, *, required: bool
    ) -> str:
        """Report a step failure and ask what to do: retry / skip / abort.

        Under ``--yes``: one automatic retry, then abort (required steps) or
        skip (optional ones). The retry budget is tracked per-instance so a
        step that keeps failing cannot loop forever.
        """
        self.say(f"✗ {title} failed: {detail}")
        if remediation:
            self.say(f"  fix: {remediation}")

        if self.assume_yes:
            budget_attr = "_auto_retries"
            used = getattr(self, budget_attr, set())
            if title not in used:
                used.add(title)
                setattr(self, budget_attr, used)
                self.say("→ retrying once (--yes) …")
                return "retry"
            return "abort" if required else "skip"

        choices = {"r": "etry", "s": "kip", "a": "bort"}
        return {"r": "retry", "s": "skip", "a": "abort"}[
            self.choose("What now?", choices, "r")
        ]
