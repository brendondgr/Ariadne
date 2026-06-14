"""Source contract inspection for KG builder datasets."""

from utils.kg_builder.source.capec import (
    CAPEC_BUILD_SCOPE,
    CAPEC_NAMESPACE,
    CAPEC_REQUIRED_COLLECTIONS,
    CapecSourceContract,
    inspect_capec_source,
    resolve_capec_metadata_path,
    resolve_capec_xml_path,
)

__all__ = [
    "CAPEC_BUILD_SCOPE",
    "CAPEC_NAMESPACE",
    "CAPEC_REQUIRED_COLLECTIONS",
    "CapecSourceContract",
    "inspect_capec_source",
    "resolve_capec_metadata_path",
    "resolve_capec_xml_path",
]
