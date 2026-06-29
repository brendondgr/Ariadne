#!/usr/bin/env python3
"""Specialist error hierarchy.

A small, explicit hierarchy so the scaffold loop can distinguish the failure
that should trigger a redraft (validation) from the one that should abort the
run (execution / intake), and so callers can catch a single base class.
"""

from __future__ import annotations


class SpecialistError(Exception):
    """Base class for every specialist failure."""


class IntakeError(SpecialistError):
    """The filtered task does not target this specialist's source."""


class ValidationError(SpecialistError):
    """A drafted query failed the deterministic pre-run gate."""


class ExecutionError(SpecialistError):
    """The bounded, read-only query failed at the database."""


class NormalizationError(SpecialistError):
    """Raw results could not be shaped into the shared evidence schema."""
