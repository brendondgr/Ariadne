#!/usr/bin/env python3
"""Normalized types every Ariadne call site sees, whatever the backend is.

The four backends disagree about almost everything and announce almost none of
it. Anthropic hoists the system prompt out of ``messages`` and 400s if you leave
it in; Gemini calls the container ``contents``, the assistant role ``model``, and
returns 200 with no candidates for a blocked prompt; OpenAI streams no usage at
all unless asked; llama.cpp reports the context window the model was *trained*
with rather than the one it is running. Every one of those is a silent failure —
the tell is an absence, not an error.

So the translation lives in one place (``utils/llm/adapters``) and application
code touches only what is in this module. The rule the adapters follow: an
adapter is *pure*. It builds a request and parses a response; it never opens a
socket. That is what makes each backend's real response shape testable offline,
and it keeps timeout and retry policy in exactly one file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class LLMUnavailable(RuntimeError):
    """The model could not be reached, or produced nothing usable.

    Deliberately one exception rather than a hierarchy. Every caller in this
    codebase does the same thing with it — fall back to the deterministic path —
    and a taxonomy nobody branches on is a taxonomy that rots.
    """


@dataclass(frozen=True)
class Message:
    """One chat turn. ``role`` is ``system``, ``user`` or ``assistant``.

    The ``system`` role is normalized *here* and split out per-provider by the
    adapter, because Anthropic and Gemini both reject it inside the message list.
    """

    role: str
    content: str

    @classmethod
    def system(cls, content: str) -> "Message":
        return cls("system", content)

    @classmethod
    def user(cls, content: str) -> "Message":
        return cls("user", content)

    @classmethod
    def assistant(cls, content: str) -> "Message":
        return cls("assistant", content)

    @classmethod
    def from_dicts(cls, messages: list[dict[str, str]]) -> list["Message"]:
        """Adapt the ``[{"role":…, "content":…}]`` shape the codebase already uses."""
        return [cls(m.get("role", "user"), m.get("content", "")) for m in messages]


@dataclass(frozen=True)
class Usage:
    """Token accounting, zero-filled when the server omits it.

    Absent usage is normal, not exceptional: OpenAI sends none while streaming
    unless ``include_usage`` is set, and several local servers never send it.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @property
    def reported(self) -> bool:
        """Whether the server actually told us anything."""
        return bool(self.prompt_tokens or self.completion_tokens or self.total_tokens)


#: ``finish_reason`` meaning "stopped at the output limit" — the content is
#: truncated, not complete. Ignoring this is how a chopped-off answer ships.
FINISH_LENGTH = "length"


@dataclass(frozen=True)
class ChatResult:
    """One completion plus the signals needed to tell truncation from an answer.

    ``content`` is normalized to a string: several servers return ``null`` on a
    length stop, and a caller that does ``.strip()`` on that gets an
    ``AttributeError`` far from the cause.
    """

    content: str
    finish_reason: str = ""
    usage: Usage = field(default_factory=Usage)
    model: str = ""
    #: The untouched provider response — the escape hatch for anything this
    #: abstraction does not cover.
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def truncated(self) -> bool:
        """True when the model stopped because it ran out of output budget."""
        return self.finish_reason == FINISH_LENGTH


@dataclass(frozen=True)
class ModelInfo:
    """One model a server says it serves.

    Every field but ``id`` may be empty. Code that *requires* a context window
    breaks the first time it meets an OpenAI endpoint, which reports ids and
    nothing else and never has reported more.
    """

    id: str
    display_name: str = ""
    context_window: int | None = None
    max_output_tokens: int | None = None
    family: str = ""
    #: How the metadata above was obtained: ``server-reported``,
    #: ``inferred-from-id``, or ``configured-fallback``. Not decoration — a UI
    #: that disables a control based on a *guess* is worse than one that lets the
    #: user try and shows the error.
    source: str = "server-reported"
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        """What the dropdown shows: the id, plus whatever is actually known."""
        bits: list[str] = []
        if self.context_window:
            bits.append(f"{self.context_window // 1024}K ctx")
        if self.meta.get("parameter_size"):
            bits.append(str(self.meta["parameter_size"]))
        name = self.display_name or self.id
        return f"{name} ({', '.join(bits)})" if bits else name


#: The three distinct empty states. Conflating them is what makes a settings
#: page frustrating: "no models" and "wrong port" need different fixes, and
#: telling someone to check their port when the server answered fine wastes
#: their afternoon.
UNREACHABLE = "unreachable"
EMPTY = "empty"
NO_LISTING = "no-listing"


@dataclass(frozen=True)
class DiscoveryResult:
    """The outcome of asking a server what it serves. **Never raises.**

    An unreachable local server is a normal operating state, not an exception.
    Nothing is wrong with our backend when someone's GPU box is off, so the HTTP
    layer returns 200 with ``ok: false`` and the UI renders an empty state rather
    than an error banner.
    """

    ok: bool
    models: list[ModelInfo] = field(default_factory=list)
    #: One of :data:`UNREACHABLE`, :data:`EMPTY`, :data:`NO_LISTING`, or "" when ok.
    state: str = ""
    #: Human-readable and safe to show verbatim.
    reason: str = ""

    @classmethod
    def found(cls, models: list[ModelInfo]) -> "DiscoveryResult":
        if not models:
            return cls(
                ok=True,
                state=EMPTY,
                reason="Connected, but the server advertises no models.",
            )
        return cls(ok=True, models=models)

    @classmethod
    def unreachable(cls, host: str, detail: str) -> "DiscoveryResult":
        return cls(
            ok=False,
            state=UNREACHABLE,
            reason=f"Could not reach {host} — is it running? ({detail})",
        )

    @classmethod
    def no_listing(cls, detail: str = "") -> "DiscoveryResult":
        return cls(
            ok=True,
            state=NO_LISTING,
            reason=(
                "This endpoint does not support model listing — type the model "
                "name manually." + (f" ({detail})" if detail else "")
            ),
        )


@dataclass(frozen=True)
class ProbeResult:
    """The verdict of the Settings "Test" button.

    Deliberately stronger than a reachability check. This project has already
    been burned by a server whose port was open and whose ten replies carried no
    ``choices`` key at all, because vLLM was still loading weights — so a passing
    test means a real completion came back with real content, not that a socket
    opened.
    """

    ok: bool
    #: Round-trip time for the completion, in milliseconds.
    latency_ms: int = 0
    #: The model the server said answered, which is not always the one asked for.
    model: str = ""
    #: Verbatim failure text. Shown to the operator as-is; a summarized error is
    #: an error you cannot act on.
    reason: str = ""
    usage: Usage = field(default_factory=Usage)

    @property
    def summary(self) -> str:
        if self.ok:
            return f"OK — {self.model or 'model'} answered in {self.latency_ms} ms"
        return self.reason or "Failed"
