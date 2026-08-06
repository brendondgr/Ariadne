"""The manifest schema — section 3.1 of ``AGENT_INSTRUCTIONS.md``.

Undocumented hyperparameters and unrecorded seeds are the field's documented
reproducibility failure modes, so every one of them is a required field here.
The schema is deliberately permissive about *unknown* and strict about *absent*:
``code.commit: unknown`` validates, a missing ``code`` block does not. A
back-filled experiment that admits three gaps is worth more than one that
invents ten values.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

Status = Literal["planned", "running", "complete", "failed", "superseded"]

#: Statuses that mean the run is over and its numbers are final.
TERMINAL_STATUSES: frozenset[str] = frozenset({"complete", "failed", "superseded"})

_ID_RE = r"^EXP-\d{4}-\d{2}-\d{3}$"
_HASH_RE = r"^(sha256|md5):[0-9a-f]{32,64}$"


class ManifestError(Exception):
    """Raised when a manifest cannot be read or does not satisfy the schema."""


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Code(_Base):
    commit: str
    branch: str
    entrypoint: str
    dirty: bool = False


class Config(_Base):
    path: str | None = None
    hash: str | None = None

    @field_validator("hash")
    @classmethod
    def _hash_shape(cls, value: str | None) -> str | None:
        return _check_hash(value, "config.hash")


class Data(_Base):
    name: str
    version: str
    split: str | None = None
    n_examples: int = Field(ge=0)
    dvc_path: str | None = None
    hash: str | None = None

    @field_validator("hash")
    @classmethod
    def _hash_shape(cls, value: str | None) -> str | None:
        return _check_hash(value, "data.hash")


class Environment(_Base):
    python: str
    lockfile: str | None = None
    container: str | None = None


class Compute(_Base):
    hardware: str
    wall_clock_hours: float | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)


class Llm(_Base):
    model: str
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    prompt_files: list[str] = Field(default_factory=list)
    prompt_hash: str | None = None
    tool_schema_hash: str | None = None
    total_input_tokens: int | None = None
    total_output_tokens: int | None = None
    nondeterminism_note: str | None = None


class MetricValue(_Base):
    mean: float
    std: float | None = None
    n: int = Field(ge=1)


class Metrics(_Base):
    primary: str | None = None
    values: dict[str, MetricValue] = Field(default_factory=dict)


class Manifest(_Base):
    """A single experiment's machine-readable record."""

    id: str = Field(pattern=_ID_RE)
    slug: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    title: str = Field(min_length=1)
    status: Status
    date_started: _dt.date
    date_completed: _dt.date | None = None
    authors: list[str] = Field(default_factory=list)

    purpose: str = Field(min_length=1)
    hypothesis: str = Field(min_length=1)

    code: Code
    config: Config = Field(default_factory=Config)
    data: Data
    seeds: list[int] = Field(default_factory=list)
    n_runs: int = Field(ge=1)
    environment: Environment
    compute: Compute

    llm: Llm | None = None

    metrics: Metrics = Field(default_factory=Metrics)
    baselines_compared: list[str] = Field(default_factory=list)
    statistical_test: str | None = None

    supports_claims: list[str] = Field(default_factory=list)
    figures: list[str] = Field(default_factory=list)
    supersedes: str | None = None
    superseded_by: str | None = None
    related: list[str] = Field(default_factory=list)

    @field_validator("supports_claims")
    @classmethod
    def _claim_shape(cls, value: list[str]) -> list[str]:
        bad = [c for c in value if not c.startswith("C-")]
        if bad:
            raise ValueError(f"claim IDs must look like C-001, got {bad}")
        return value

    @field_validator("supersedes", "superseded_by")
    @classmethod
    def _exp_ref_shape(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("EXP-"):
            raise ValueError(f"experiment references must start with EXP-, got {value!r}")
        return value

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    @property
    def primary_value(self) -> float | None:
        """The headline number, or None if there is no primary metric recorded."""
        if not self.metrics.primary:
            return None
        entry = self.metrics.values.get(self.metrics.primary)
        return entry.mean if entry else None


def _check_hash(value: str | None, field: str) -> str | None:
    import re

    if value is None:
        return None
    if not re.match(_HASH_RE, value):
        raise ValueError(f"{field} must look like sha256:<hex> or md5:<hex>, got {value!r}")
    return value


def load_manifest(path: Path) -> Manifest:
    """Read and validate one ``manifest.yaml``.

    Raises ``ManifestError`` with the offending file named, because a schema
    error reported without its path is a scavenger hunt across N experiments.
    """
    try:
        raw: Any = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise ManifestError(f"{path}: cannot read as YAML — {exc}") from exc
    if not isinstance(raw, dict):
        raise ManifestError(f"{path}: expected a YAML mapping, got {type(raw).__name__}")
    try:
        return Manifest.model_validate(raw)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        raise ManifestError(f"{path}: {details}") from exc
