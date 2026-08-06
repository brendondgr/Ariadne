"""The research record: schema, validation, indexing, and scaffolding.

``docs/research/`` is the only place a research finding is allowed to live. This
package is what stops that convention decaying — it defines the manifest schema,
validates every experiment against it, regenerates ``INDEX.md``, and scaffolds
new experiments with their provenance already captured.

The contract this package enforces is ``docs/research/AGENT_INSTRUCTIONS.md``.
When the two disagree, the document is authoritative and this package is the
bug.
"""

from utils.research_record.manifest import (
    Manifest,
    ManifestError,
    load_manifest,
)

__all__ = ["Manifest", "ManifestError", "load_manifest"]
