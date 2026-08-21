#!/usr/bin/env python3
"""A seeded synthetic tenant conforming to a declared catalog.

See :mod:`utils.kg_builder.synthetic.generator` for the four properties that
shape the design, and :mod:`utils.kg_builder.synthetic.spec` for why the
blueprint is written upstream of the graph rather than derived from it.
"""

from .generator import DEFAULT_SIZES, generate
from .spec import PlantedPath, TenantSpec

__all__ = ["DEFAULT_SIZES", "PlantedPath", "TenantSpec", "generate"]
