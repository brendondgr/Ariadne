"""The service must never take a module import lock on a request thread.

Regression guard for a live wedge on 2026-09-07: a request stalled inside
``build_specialist``'s lazy import while holding the import lock for
``utils.specialists.cypher.specialist``, and every later query blocked forever
in ``_lock_unlock_module``. /api/health stopped answering too; only a restart
cleared it. Importing both backends at service import removes the hazard.
"""

from __future__ import annotations

import sys


def test_importing_the_app_resolves_both_specialist_backends() -> None:
    import api.main  # noqa: F401 - the import is the subject

    assert "utils.specialists.cypher.specialist" in sys.modules
    assert "utils.specialists.gremlin.specialist" in sys.modules


def test_build_specialist_takes_no_new_import_after_startup() -> None:
    """Its lazy imports must already be satisfied, so the call cannot block."""
    import api.main  # noqa: F401

    before = set(sys.modules)
    from utils.specialists.cypher.specialist import build_cypher_specialist  # noqa: F401
    from utils.specialists.gremlin.specialist import build_gremlin_specialist  # noqa: F401

    assert set(sys.modules) == before, "a request-time import would still be possible"
