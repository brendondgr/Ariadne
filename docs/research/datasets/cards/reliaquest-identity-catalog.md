# Dataset Card — ReliaQuest Identity Graph Catalog

**Version:** delivered 2026-08-21 · **Size:** 72 node types, 21 edge labels, 60 typed triples, 779 node attributes, 118 edge attributes · **Records:** none
**Used by:** EXP-2026-08-011

---

## What it is

The **schema** of ReliaQuest's production customer graph — not the graph. Two CSV
exports plus the SQL that produced them, supplied by the funder of this project
(ReliaQuest Innovation Challenge Fund, Challenge Three) as part of the challenge
data drop.

It is the first non-MITRE schema this codebase has had access to, which is the
whole of its research value: every correctness figure on record was measured on
ATT&CK and CAPEC, the two schemas the code was developed against.

| File | Size | SHA-256 |
|---|---|---|
| `node_attributes.csv` | 33,713 B | `8089788527395324eaf74458ea157023796c8ee754805cf40ce19accf80cbef1` |
| `relationship_attributes.csv` | 5,712 B | `e73c0d84b206367e7130b22a4407d650b617c1e1c7f7c0919543792ced23a964` |
| `customer_xref.sql.rtf` | 720 B | the two queries that produced the above |

## What is in it

Five identity and cloud planes: Active Directory, Entra, Okta, AWS (including
SSO), and GCP.

| Element | Count | Examples |
|---|---|---|
| Node types | 72 | `USER`, `DEVICE`, `DOMAIN`, `GPO`, `OU`, `AD_CERT_TEMPLATE`, `OKTA_API_TOKEN`, `ENTRA_SERVICE_PRINCIPAL`, `AWS_SSO_USER`, `GCP_BINDING` |
| Edge labels | 21 | `DC_SYNC`, `WRITE_DACL`, `ADD_KEY_CREDENTIAL_LINK`, `GENERIC_ALL`, `ALL_EXTENDED_RIGHTS`, `SAME_FOREST_TRUST`, `MEMBER_OF` |
| Typed triples | 60 | `GROUP -DC_SYNC-> DOMAIN`, `DEVICE -RUNS_AS-> USER` |
| Node attributes | 779 | 131 on `USER` alone; typed `STRING` / `BOOLEAN` / `INTEGER` / `LIST_STRING` |
| Edge attributes | 118 | `is_inherited`, `principal_type`, `sid_filtering` |

The edge vocabulary is BloodHound-shaped: these are privilege-escalation and
attack-path relationships, not inventory relationships.

Two properties of the delivery are worth recording because they are useful
rather than defective:

* **Declared value types.** The existing schema path derives label → property
  keys by scanning instances and learns nothing about types. This catalog
  declares them. That is strictly more than a scan produces.
* **A real spelling collision.** Both `ENTRA_LICENCE` and `ENTRA_LICENSE` appear
  as distinct node types. This is preserved verbatim and must never be cleaned:
  it is a free disambiguation test case, and tidying it would mean evaluating
  against a schema cleaner than the customer actually has.

## What is **not** in it

**No customer records of any kind.** No nodes, no edges, no tenant, no
identifiers. Only the catalog.

This is deliberate on ReliaQuest's part — customer data cannot be shared — and it
is the reason EXP-2026-08-011 generates synthetic instances. It is also the
reason the delivery suits this project specifically: Ariadne's stated design
consumes schema and metadata rather than data, so a schema-only delivery is its
native input rather than a shortfall.

## ⚠️ The export is truncated, and permanently so

`customer_xref.sql.rtf` shows both queries use an **inner** join to
`customer_attribute_catalog`:

```sql
select distinct e.source_node_type, e.edge_label, e.target_node_type, a.attribute_name, a.value_type
from customer_edge_catalog e
    join customer_attribute_catalog a on e.uuid = a.edge_uuid;
```

Any edge type carrying **no attributes** therefore never reached the file. The
evidence is structural rather than inferred:

* There is no `USER -MEMBER_OF-> GROUP` triple. `MEMBER_OF` appears only as
  `USER -MEMBER_OF-> GCP_GROUP` and `USER -MEMBER_OF-> OKTA_GROUP`.
* 48 of the 60 triples have `GROUP` as their source.

Together those describe an Active Directory graph in which no user belongs to any
group — which cannot be the real schema.

**The operator confirmed on 2026-08-21 that no corrected export will be
supplied.** The truncation is therefore a permanent property of this dataset. Any
experiment using it must:

1. Treat the 60 delivered triples as the authoritative declared set, unmodified.
2. Carry any edge added to make the graph functional in a separate `inferred`
   block, marked in the artifact and in the source card, never merged into the
   declared set.
3. Report results split by declared-vs-inferred so the two cannot be confused.

A corrected export would have been `select distinct source_node_type, edge_label,
target_node_type from customer_edge_catalog` with no join at all.

## Licence and handling

Supplied by the funder under the challenge agreement. **Not public, not
redistributable, and not committed to this repository.** The CSVs live outside
the repo tree and are referenced by checksum only, in the same spirit as the
git-ignored MITRE downloads pinned in `data/versions.json`.

Because it contains no customer records, the catalog carries no personal data —
but it does describe a real production system's structure, so the checksums and
counts recorded here are the only parts that belong in the research record.

## Related

The same delivery included a LlamaIndex vector store over the leaked Black Basta
ransomware chat logs (527 MB, 22,290 chunks, embeddings tied to an
`azure:text-embedding-3-small` deployment behind ReliaQuest's API gateway). It
shares no entities with anything else in this project and is **not used by any
experiment**. It is noted here so its existence is on record and its exclusion is
a decision rather than an oversight.
