## What this document says

The ATT&CK Enterprise dataset is a STIX-based JSON bundle used as the machine-readable source for ATT&CK content. The important idea for your KG work is that it is already graph-shaped: most entries are node-like STIX objects, and explicit `relationship` objects are the edges. 

## How to read the JSON

Treat the file as one top-level `bundle` object with an `objects` array inside it. Your first step is to split `objects` by `type`:

* `relationship` → edge
* everything else relevant → node

For techniques, sub-techniques, groups, software, mitigations, campaigns, data sources, and so on, the object itself contains the node data. The `id` field is the stable identifier to use as the primary key in your graph. The ATT&CK human-readable ID, like `T1566`, is usually found in `external_references`. 

## What to convert nodes into

Use this basic mapping:

* `x-mitre-tactic` → `Tactic`
* `attack-pattern` → `Technique`
* `intrusion-set` → `Group`
* `malware` / `tool` → `Software`
* `course-of-action` → `Mitigation`
* `campaign` → `Campaign`
* `x-mitre-data-source` → `DataSource`
* `x-mitre-data-component` → `DataComponent`
* `x-mitre-asset` → `Asset`
* `x-mitre-matrix` → `Matrix` 

A technique and a sub-technique both use `attack-pattern`. You distinguish sub-techniques using `x_mitre_is_subtechnique: true` and the ATT&CK ID format such as `T1566.001`. 

## What to convert edges into

Each STIX `relationship` object becomes a directed KG edge. The key field is `relationship_type`, which should become the edge label. Common examples:

* `Group` → `uses` → `Technique`
* `Group` → `uses` → `Software`
* `Software` → `uses` → `Technique`
* `Mitigation` → `mitigates` → `Technique`
* `Campaign` → `uses` → `Technique`
* `Campaign` → `attributed-to` → `Group` 

For parent/child technique structure, the document treats this as a `HAS_SUBTECHNIQUE`-style relationship in the KG, derived from the ATT&CK data model. 

## Special rule for tactics

There is no normal relationship object for tactic-to-technique links. Instead, you must read `kill_chain_phases` on each technique and match the `phase_name` values to ATT&CK tactic short names. That is how you derive:

* `Tactic` → `HAS_TECHNIQUE` → `Technique` 

## Node properties worth preserving

The document recommends keeping these as node attributes:

* `id`
* `name`
* `description`
* `external_references`
* `x_mitre_platforms`
* `x_mitre_version`
* `x_mitre_deprecated`
* `revoked` 

## Filters you should apply before loading

The file warns that the Enterprise bundle contains deprecated and revoked objects. For a clean KG, filter out nodes where:

* `revoked == true`
* `x_mitre_deprecated == true` 

## Important note about the file format

The text also says that if the file looks like unreadable binary garbage, it is likely gzip-compressed data being read as plain text. In that case, decompress it first or load it with gzip-aware code before parsing as JSON. 

## Practical conversion rule set

For your reference guide, the core logic is:

1. Load the bundle.
2. Iterate through `objects`.
3. Create KG nodes for every relevant STIX object.
4. Create KG edges for every `relationship` object.
5. Derive tactic-to-technique edges from `kill_chain_phases`.
6. Keep ATT&CK IDs and STIX UUIDs together so you can reconcile human labels and stable graph identifiers.
7. Filter deprecated/revoked content unless you explicitly need historical objects. 