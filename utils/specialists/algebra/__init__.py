"""The operator algebra (Era 2, Step 9): retrieval operations with one fixed meaning.

The semantics are in ``docs/era-2-expansion/operator-algebra.md``. This package
holds:
- the internal form, one module per operator;
- its validation against a card (``validate.py``);
- the front ends that turn today's ``TypedStep`` (``from_typed_step.py``) and the
  kill-test v3 requests (``from_v3.py``) into it.

The compilers live beside the builders, in ``utils/specialists/cypher/compile.py``
and ``gremlin/compile.py``.
"""

from .ir import *  # noqa: F401,F403
from .ir import __all__  # noqa: F401
