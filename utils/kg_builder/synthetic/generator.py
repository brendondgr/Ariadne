#!/usr/bin/env python3
"""Generate a tenant that obeys a declared catalog, and record what it decided.

The point of this module is EXP-2026-08-011: ReliaQuest supplied a schema and no
records, so instances have to come from somewhere before anything can be
queried. Four properties are non-negotiable, and each shapes the code:

**Conformance is structural, not reviewed.** :meth:`_Builder.edge` refuses any
edge the catalog does not permit. The graph therefore cannot drift from the
schema, because a non-conforming edge is never written in the first place rather
than being caught by a checker afterwards.

**Determinism.** One :class:`random.Random`, seeded once, threaded everywhere.
Same seed, byte-identical output. This is what makes the primary metric
re-runnable without a language model or a network.

**Declared and inferred edges stay separable.** Every edge records which it is,
because three of the edge kinds are this project's reconstruction of what the
truncated export dropped, and any result traversing one is confounded.

**The blueprint is written, not derived.** Every decision goes into
:class:`~utils.kg_builder.synthetic.spec.TenantSpec` as it is made. Gold answers
come from there, never from the loaded graph — see that module for why.

Scale is chosen to sit near ATT&CK's 4,369 nodes so retrieval breadth is
comparable between the two domains and no difference between them is a size
effect.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable

from ..catalog.declared import DECLARED, INFERRED, DeclaredCatalog
from . import idshapes
from .spec import PlantedPath, TenantSpec

# Tenant shape. Deliberately modest and legible: enough structure for multi-hop
# questions, few enough entities that a failure can be read by hand.
DEFAULT_SIZES: dict[str, int] = {
    "USER": 600,
    "DEVICE": 240,
    "GROUP": 72,
    "OU": 12,
    "CONTAINER": 8,
    "GPO": 14,
    "DOMAIN": 3,
    "OKTA_GROUP": 18,
    "OKTA_APPLICATION": 22,
    "ENTRA_GROUP": 16,
    "GCP_GROUP": 10,
    "GCP_BINDING": 24,
}

# Every other declared node type gets this many instances. 58 of the catalog's 72
# node types appear in no declared triple at all -- the same inner-join
# truncation seen from the node side rather than the edge side. They are
# populated anyway, for two reasons. They are real declared types with real
# declared attributes, so a tenant that omitted them would be less faithful to
# the catalog, not more. And they are the honest surface for the abstention
# measurement: a question about ENTRA_LICENSE should be answered "that label
# exists and has no traversable relationship", which is a different and better
# answer than either a guess or a blank.
RESIDUAL_LABEL_SIZE = 5

_FIRST = [
    "ada", "brian", "chen", "dara", "elena", "farid", "grace", "hana", "ivan",
    "jsmith", "kiran", "lena", "marco", "nadia", "omar", "priya", "quinn",
    "rosa", "sven", "tariq", "uma", "vik", "wren", "xu", "yara", "zane",
]
_LAST = [
    "alvarez", "brennan", "cho", "duarte", "eriksen", "fontaine", "gupta",
    "haddad", "ito", "jensen", "kowalski", "lindqvist", "moreau", "novak",
    "okafor", "petrov", "quiroga", "rasmussen", "silva", "tanaka",
]
_GROUP_NAMES = [
    "Domain Admins", "Enterprise Admins", "Helpdesk", "Server Operators",
    "Backup Operators", "Account Operators", "Workstation Admins",
    "Finance Readers", "HR Records", "Security Engineering", "Network Ops",
    "Database Admins", "Tier1 Support", "Tier2 Support", "Contractors",
    "Service Accounts", "Certificate Managers", "Exchange Admins",
]
_TIERS = ["tier0", "tier1", "tier2"]


@dataclass
class _Builder:
    """Accumulates the graph and the blueprint together, refusing bad edges."""

    catalog: DeclaredCatalog
    spec: TenantSpec
    rng: random.Random
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    _edge_keys: set[tuple[str, str, str]] = field(default_factory=set)

    def node(self, label: str, name: str, properties: dict[str, Any]) -> str:
        """Create a node, keeping only property keys the catalog declares.

        Filtering rather than raising is deliberate here (unlike edges): a
        generator that invents a plausible property for a label it does not know
        well should silently produce a smaller node, not abort the tenant. The
        conformance test asserts the filter worked.
        """
        declared = self.catalog.node_attributes.get(label, {})
        kept = {k: v for k, v in properties.items() if k in declared}
        node_id = properties.get("__id") or idshapes.guid(self.rng)
        self.nodes.append(
            {
                "id": node_id,
                "label": label,
                "labels": [label],
                "name": name,
                "properties": kept,
            }
        )
        self.spec.add_node(node_id, label, name, kept)
        return node_id

    def edge(self, source_id: str, edge_label: str, target_id: str) -> None:
        """Create an edge, or refuse it.

        The catalog is the authority. An edge it does not permit is a bug in the
        generator, not a datum, so this raises rather than skipping — a silently
        dropped edge would leave the blueprint and the graph disagreeing, which
        is the one failure this whole design exists to prevent.
        """
        source_label = self.spec.label_of(source_id)
        target_label = self.spec.label_of(target_id)
        if not self.catalog.permits(source_label, edge_label, target_label):
            raise ValueError(
                f"catalog does not permit {source_label} -{edge_label}-> {target_label}"
            )
        # Idempotent on (source, edge, target). A planted chain frequently wants
        # an edge a random pass already created -- `USER -MEMBER_OF-> GROUP` and
        # `GROUP -DC_SYNC-> DOMAIN` both did on the first real run. Writing it
        # twice is not two facts, and Neo4j MERGEs the pair back to one on load,
        # so the blueprint would claim 3,816 edges against a store holding
        # 3,814. That divergence is exactly what the blueprint exists to make
        # impossible, and it is caught here rather than being discovered as a
        # gold mismatch later.
        key = (source_id, edge_label, target_id)
        if key in self._edge_keys:
            return
        self._edge_keys.add(key)

        origin = (
            INFERRED
            if any(
                t.key() == (source_label, edge_label, target_label)
                for t in self.catalog.inferred_triples()
            )
            else DECLARED
        )
        self.edges.append(
            {
                "id": idshapes.guid(self.rng),
                "type": edge_label,
                "source_id": source_id,
                "target_id": target_id,
                "properties": {},
            }
        )
        self.spec.add_edge(source_id, edge_label, target_id, origin)

    def supports(self, source_label: str, edge_label: str, target_label: str) -> bool:
        """Does the catalog permit this edge kind at all?

        Used to guard whole topology blocks. The distinction against
        :meth:`edge` matters: `edge` raising means the generator tried to build
        something the schema forbids, which is a bug. `supports` returning False
        means the catalog is simply smaller than the topology this generator
        knows how to build -- true of every hand-written test fixture, and it
        must not abort the tenant.
        """
        return self.catalog.permits(source_label, edge_label, target_label)

    def pick(self, items: list[str], n: int) -> list[str]:
        if n >= len(items):
            return list(items)
        return self.rng.sample(items, n)


def _value_for(b: _Builder, label: str, attr) -> Any:
    """A catalog-shaped value for one declared attribute.

    Driven entirely by the declared type and the attribute's own name, because
    the alternative -- hand-written property dicts per label -- silently loses
    every key whose spelling this project guessed wrong. That failure already
    happened once here: the ReliaQuest catalog keys Active Directory objects as
    ``active_directory__user_uid``, not ``objectsid``, so a hand-written
    ``objectsid`` was filtered out and the tenant carried no SID-shaped values
    at all, quietly making EXP-2026-08-011's H4 easier than it should be.

    Identifier shape follows the platform prefix in the *label*, which is how a
    real tenant works: an AWS role is keyed by an ARN, an Okta object by an
    opaque base-62 id, an Entra object by a GUID, an AD object by a SID.
    """
    key = attr.name
    lowered = key.lower()
    slug = label.lower().replace("_", "-")

    if attr.value_type == "BOOLEAN":
        return b.rng.random() < 0.3
    if attr.value_type == "INTEGER":
        return b.rng.randrange(1, 400)
    if attr.value_type == "LIST_STRING":
        return [f"{slug}-tag-{b.rng.randrange(1, 6)}"]

    is_identifier = any(part in lowered for part in ("uid", "_id", "arn", "sid"))
    if is_identifier:
        if label.startswith("AWS"):
            return idshapes.arn(b.rng, "iam", slug, f"{slug}-{b.rng.randrange(1, 999)}")
        if label.startswith("OKTA"):
            return idshapes.okta_id(b.rng, "0oa")
        if label.startswith("ENTRA"):
            return idshapes.entra_object_id(b.rng)
        if label.startswith("GCP"):
            return idshapes.gcp_resource(b.rng, slug, f"{slug}-{b.rng.randrange(1, 999)}")
        if lowered.startswith(("ad__", "active_directory__")):
            return idshapes.sid(b.rng)
        return idshapes.guid(b.rng)
    if "principalname" in lowered or "upn" in lowered:
        return idshapes.upn(b.rng, f"u{b.rng.randrange(1000, 9999)}")
    if "ldap_dn" in lowered or "distinguished" in lowered:
        return idshapes.distinguished_name(b.rng, f"cn{b.rng.randrange(100, 999)}")
    if "hostname" in lowered or "dnsname" in lowered:
        return idshapes.dns_name(b.rng, f"host{b.rng.randrange(100, 999)}")
    if "name" in lowered:
        return f"{slug}-{b.rng.randrange(1, 999)}"
    return f"{slug}-{key.split('.')[-1]}-{b.rng.randrange(1, 999)}"


def _fill(
    b: _Builder,
    label: str,
    name: str,
    overrides: dict[str, Any] | None = None,
) -> str:
    """Create one node, filling every declared attribute, then applying overrides.

    Overrides carry meaning a generic filler cannot -- a user's department, a
    group's privileged flag -- and are applied only for keys the catalog
    actually declares, so a misspelled override changes nothing rather than
    corrupting the node.
    """
    declared = b.catalog.node_attributes.get(label, {})
    props: dict[str, Any] = {
        attr.name: _value_for(b, label, attr) for attr in sorted(declared.values())
    }
    for key, value in (overrides or {}).items():
        if key in declared:
            props[key] = value
    props["__id"] = idshapes.guid(b.rng)
    return b.node(label, name, props)


def _make_users(b: _Builder, count: int) -> list[str]:
    ids: list[str] = []
    for i in range(count):
        sam = f"{b.rng.choice(_FIRST)[0]}{b.rng.choice(_LAST)}{i}"
        ids.append(
            _fill(
                b,
                "USER",
                sam,
                {
                    "user.name": sam,
                    "user.ldap_person.department": b.rng.choice(
                        ["Finance", "Engineering", "HR", "Sales", "IT", "Legal"]
                    ),
                    "user.ldap_person.location.city": b.rng.choice(
                        ["Tampa", "Austin", "Dublin", "Toronto", "Singapore"]
                    ),
                    "entra__onPremisesSamAccountName": sam,
                    "active_directory__userprincipalname": idshapes.upn(b.rng, sam),
                    "ad__userprincipalname": idshapes.upn(b.rng, sam),
                    "ad__passwordnotreqd": b.rng.random() < 0.04,
                },
            )
        )
    return ids


def _make_groups(b: _Builder, count: int) -> list[str]:
    ids: list[str] = []
    for i in range(count):
        base = _GROUP_NAMES[i] if i < len(_GROUP_NAMES) else f"App Access {i:03d}"
        ids.append(
            _fill(
                b,
                "GROUP",
                base,
                {
                    "group.name": base,
                    # The first six are the privileged tier the planted attack
                    # chains escalate toward.
                    "group.privileges": i < 6,
                    "resource.name": base,
                },
            )
        )
    return ids


def _make_devices(b: _Builder, count: int) -> list[str]:
    ids: list[str] = []
    for i in range(count):
        host = f"{b.rng.choice(['wks', 'srv', 'dc', 'lap'])}{i:03d}"
        ids.append(
            _fill(
                b,
                "DEVICE",
                host,
                {
                    "active_directory__device_os_name": b.rng.choice(
                        ["Windows 11", "Windows Server 2022", "Ubuntu 24.04"]
                    ),
                    "resource.name": host,
                },
            )
        )
    return ids


def _make_simple(
    b: _Builder,
    label: str,
    count: int,
    namer: Callable[[int], str],
    props: Callable[[int, str], dict[str, Any]] | None = None,
) -> list[str]:
    ids: list[str] = []
    for i in range(count):
        name = namer(i)
        overrides: dict[str, Any] = {"resource.name": name, "org.ou_name": name}
        if props is not None:
            overrides.update(props(i, name))
        ids.append(_fill(b, label, name, overrides))
    return ids


def _make_residual(b: _Builder, label: str, count: int) -> list[str]:
    """Populate a declared label that participates in no declared edge.

    58 of the catalog's 72 node types are in this position -- the same
    inner-join truncation seen from the node side. They are real declared types
    with real declared attributes, and they are the honest surface for the
    abstention measurement: a question about ENTRA_LICENSE should be answered
    "that label exists and has no traversable relationship", which is a
    different and better answer than either a guess or a blank.
    """
    slug = label.lower().replace("_", "-")
    return [_fill(b, label, f"{slug}-{i:02d}") for i in range(count)]


def generate(
    catalog: DeclaredCatalog,
    seed: int = 20260821,
    sizes: dict[str, int] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], TenantSpec]:
    """Build a catalog-conformant tenant. Returns ``(nodes, edges, spec)``."""
    rng = random.Random(seed)
    spec = TenantSpec(seed=seed, catalog_name=catalog.name)
    b = _Builder(catalog=catalog, spec=spec, rng=rng, nodes=[], edges=[])
    n = dict(DEFAULT_SIZES)
    if sizes:
        n.update(sizes)

    users = _make_users(b, n["USER"])
    groups = _make_groups(b, n["GROUP"])
    devices = _make_devices(b, n["DEVICE"])
    domains = _make_simple(
        b, "DOMAIN", n["DOMAIN"],
        lambda i: f"{'corp' if i == 0 else f'sub{i}'}.{idshapes.DNS_SUFFIX}",
        lambda i, name: {
            "ad__minpwdlength": rng.choice([8, 12, 14]),
            "ad__maxpwdage": rng.choice([30, 60, 90]),
            "ad__pwdhistorylength": rng.choice([12, 24]),
            "active_directory__distinguishedname": ",".join(
                f"DC={p}" for p in name.split(".")
            ),
        },
    )
    ous = _make_simple(b, "OU", n["OU"], lambda i: f"OU-{_TIERS[i % 3]}-{i:02d}",
                       lambda i, name: {"org.ou_name": name})
    containers = _make_simple(b, "CONTAINER", n["CONTAINER"], lambda i: f"CN-Container-{i:02d}")
    gpos = _make_simple(b, "GPO", n["GPO"], lambda i: f"GPO-{i:02d}-baseline")
    okta_groups = _make_simple(b, "OKTA_GROUP", n["OKTA_GROUP"], lambda i: f"okta-group-{i:02d}",
                               lambda i, name: {"okta__resource_uid": idshapes.okta_id(rng, "00g")})
    okta_apps = _make_simple(b, "OKTA_APPLICATION", n["OKTA_APPLICATION"],
                             lambda i: f"okta-app-{i:02d}",
                             lambda i, name: {"okta__resource_uid": idshapes.okta_id(rng, "0oa")})
    entra_groups = _make_simple(b, "ENTRA_GROUP", n["ENTRA_GROUP"], lambda i: f"entra-group-{i:02d}",
                                lambda i, name: {"entra__group_uid": idshapes.entra_object_id(rng)})
    gcp_groups = _make_simple(b, "GCP_GROUP", n["GCP_GROUP"], lambda i: f"gcp-group-{i:02d}")
    gcp_bindings = _make_simple(b, "GCP_BINDING", n["GCP_BINDING"], lambda i: f"gcp-binding-{i:02d}")

    root_domain = domains[0]

    # -- every remaining declared label, so the tenant covers the catalog ---
    populated = {
        "USER", "DEVICE", "GROUP", "OU", "CONTAINER", "GPO", "DOMAIN",
        "OKTA_GROUP", "OKTA_APPLICATION", "ENTRA_GROUP", "GCP_GROUP",
        "GCP_BINDING",
    }
    for label in sorted(catalog.node_attributes):
        if label in populated:
            continue
        _make_residual(b, label, n.get(label, RESIDUAL_LABEL_SIZE))

    # -- membership: the inferred edges, and the reason they were needed ----
    # One or two memberships per user, not one to three. These edges are this
    # project's reconstruction rather than ReliaQuest's schema, so the fewer of
    # them carry the graph the less of any result they confound -- while still
    # being enough for a user to reach the 48 GROUP-sourced triples at all,
    # which is the entire reason they were inferred.
    if b.supports("USER", "MEMBER_OF", "GROUP"):
        for user in users:
            for group in b.pick(groups, rng.randrange(1, 3)):
                b.edge(user, "MEMBER_OF", group)
    # Nested groups, shallow and acyclic: group i may only nest into a group
    # earlier in the list, so no cycle can form and depth stays readable.
    if b.supports("GROUP", "MEMBER_OF", "GROUP"):
        for index, group in enumerate(groups):
            if index > 3 and rng.random() < 0.35:
                b.edge(group, "MEMBER_OF", groups[rng.randrange(0, index)])
    if b.supports("USER", "MEMBER_OF", "ENTRA_GROUP"):
        for user in b.pick(users, len(users) // 3):
            b.edge(user, "MEMBER_OF", rng.choice(entra_groups))

    # -- declared cloud membership and assignment --------------------------
    # Every block below is guarded by `supports`, because the topology this
    # generator knows how to build is larger than any one catalog. A hand-written
    # test fixture declares a handful of triples; the real delivery declares 60.
    # Guarding lets both run without the generator either aborting or having to
    # be told which catalog it is working against.
    if b.supports("USER", "MEMBER_OF", "OKTA_GROUP"):
        for user in b.pick(users, len(users) // 2):
            b.edge(user, "MEMBER_OF", rng.choice(okta_groups))
    if b.supports("USER", "MEMBER_OF", "GCP_GROUP"):
        for user in b.pick(users, len(users) // 3):
            b.edge(user, "MEMBER_OF", rng.choice(gcp_groups))
    if b.supports("USER", "APP_ASSIGNMENT", "OKTA_APPLICATION"):
        for user in b.pick(users, (2 * len(users)) // 3):
            for app in b.pick(okta_apps, rng.randrange(1, 3)):
                b.edge(user, "APP_ASSIGNMENT", app)
    if b.supports("USER", "BOUND_BY", "GCP_BINDING"):
        for user in b.pick(users, len(users) // 4):
            b.edge(user, "BOUND_BY", rng.choice(gcp_bindings))
    if b.supports("GCP_GROUP", "BOUND_BY", "GCP_BINDING"):
        for group in b.pick(gcp_groups, len(gcp_groups) // 2):
            b.edge(group, "BOUND_BY", rng.choice(gcp_bindings))

    # -- devices -----------------------------------------------------------
    if b.supports("DEVICE", "RUNS_AS", "USER"):
        for device in devices:
            b.edge(device, "RUNS_AS", rng.choice(users))

    # -- GPO links ---------------------------------------------------------
    for gpo in gpos:
        to_domain = rng.random() < 0.5
        if to_domain and b.supports("GPO", "GP_LINK", "DOMAIN"):
            b.edge(gpo, "GP_LINK", rng.choice(domains))
        elif b.supports("GPO", "GP_LINK", "OU"):
            b.edge(gpo, "GP_LINK", rng.choice(ous))

    # -- domain trusts: two of the eight homogeneous triples ---------------
    for i in range(1, len(domains)):
        if b.supports("DOMAIN", "TRUSTED_BY", "DOMAIN"):
            b.edge(domains[i], "TRUSTED_BY", domains[0])
        if b.supports("DOMAIN", "SAME_FOREST_TRUST", "DOMAIN"):
            b.edge(domains[0], "SAME_FOREST_TRUST", domains[i])

    # -- ACL edges: the bulk of the catalog, and six more homogeneous ones --
    acl_targets: dict[str, list[str]] = {
        "USER": users,
        "DEVICE": devices,
        "GROUP": groups,
        "DOMAIN": domains,
        "OU": ous,
        "CONTAINER": containers,
        "GPO": gpos,
    }
    acl_edges = [
        t
        for t in catalog.declared_triples()
        if t.source == "GROUP" and t.target in acl_targets
    ]
    for triple in acl_edges:
        pool = acl_targets[triple.target]
        # Sparse on purpose: a dense ACL graph would make every question
        # answerable by returning almost everything, which measures nothing.
        for group in b.pick(groups, max(3, len(groups) // 6)):
            for target in b.pick(pool, rng.randrange(1, 4)):
                if triple.is_homogeneous and target == group:
                    continue  # no self-loops
                b.edge(group, triple.edge, target)

    # -- planted attack chains --------------------------------------------
    planted = _plant_paths(b, users, groups, domains, root_domain)
    spec.planted_paths = planted

    return b.nodes, b.edges, spec


def _plant_paths(
    b: _Builder,
    users: list[str],
    groups: list[str],
    domains: list[str],
    root_domain: str,
) -> list[PlantedPath]:
    """Create chains a question can be asked about, and record them exactly.

    Without these, multi-hop questions would depend on chains the random ACL
    pass happened to produce, which is both unreliable and unrecorded. Planting
    them makes gold a lookup instead of a traversal, and makes the hard cases
    (homogeneous-label hops) certain to be exercised rather than likely.
    """
    paths: list[PlantedPath] = []
    inferred_keys = {t.key() for t in b.catalog.inferred_triples()}

    def record(name: str, steps: list[tuple[str, str, str]]) -> None:
        uses_inferred = any(
            (
                b.spec.label_of(s),
                edge,
                b.spec.label_of(t),
            )
            in inferred_keys
            for s, edge, t in steps
        )
        paths.append(PlantedPath(name=name, steps=steps, uses_inferred=uses_inferred))

    def plant(name: str, steps: list[tuple[str, str, str]]) -> None:
        """Create every step, or plant nothing at all.

        All-or-nothing because a half-planted chain is worse than an absent one:
        gold would name a path the graph cannot walk, and the arm would be
        marked wrong for a generator defect. A chain is skipped only when the
        catalog lacks one of its edge kinds, which is true of the small test
        fixtures and of no real delivery.
        """
        for source, edge, target in steps:
            if not b.supports(
                b.spec.label_of(source), edge, b.spec.label_of(target)
            ):
                return
        for source, edge, target in steps:
            b.edge(source, edge, target)
        record(name, steps)

    domain_admins = groups[0]
    helpdesk = groups[2]

    # 1. The canonical DCSync chain, through a nested group.
    plant(
        "dcsync-via-helpdesk",
        [
            (b.rng.choice(users), "MEMBER_OF", helpdesk),
            (helpdesk, "WRITE_DACL", domain_admins),
            (domain_admins, "DC_SYNC", root_domain),
        ],
    )

    # 2. Shadow credentials onto a user.
    cert_managers = groups[16] if len(groups) > 16 else groups[-1]
    plant(
        "shadow-credentials",
        [(cert_managers, "ADD_KEY_CREDENTIAL_LINK", b.rng.choice(users))],
    )

    # 3. GROUP -OWNS-> GROUP -GENERIC_ALL-> USER: opens on a homogeneous hop,
    #    which is the case H3 is about.
    plant(
        "owns-chain-to-user",
        [
            (groups[5], "OWNS", groups[9]),
            (groups[9], "GENERIC_ALL", b.rng.choice(users)),
        ],
    )

    # 4. Replication rights short of full DCSync.
    plant(
        "replication-rights",
        [
            (groups[10], "GET_CHANGES", root_domain),
            (groups[10], "GET_CHANGES_ALL", root_domain),
        ],
    )

    # 5. Cross-forest reach, exercising the other homogeneous pair. The trust
    #    edge already exists from the trust pass, so this chain records it as
    #    context rather than re-creating it.
    if len(domains) > 1 and b.supports("GROUP", "ALL_EXTENDED_RIGHTS", "DOMAIN"):
        trusting = groups[3]
        b.edge(trusting, "ALL_EXTENDED_RIGHTS", domains[1])
        steps = [(trusting, "ALL_EXTENDED_RIGHTS", domains[1])]
        if b.supports("DOMAIN", "TRUSTED_BY", "DOMAIN"):
            steps.insert(0, (domains[1], "TRUSTED_BY", domains[0]))
        record("cross-forest-rights", steps)

    return paths
