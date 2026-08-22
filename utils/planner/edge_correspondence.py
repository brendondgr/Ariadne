#!/usr/bin/env python3
"""Declared correspondence between identity edge types and ATT&CK techniques.

**This file is authored knowledge, not observed data, and that distinction is
the most important thing about it.**

Every other bridge in this project is a *value* join: a property on one side
holds the same string as a property on the other, and the planner discovers the
correspondence by comparing values it read out of two graphs (see
``join_keys.CANONICAL_JOIN_KEYS``). The identity graph admits no such bridge. It
contains no ATT&CK identifier anywhere — not in a property, not in a label, not
in an edge attribute — so there is nothing to join *on*.

What exists instead is a correspondence in meaning: a ``DC_SYNC`` edge **is**
the technique ATT&CK calls T1003.006. That is a claim about the world, supplied
by us, and it cannot be derived from either graph. So it is declared here, in
one reviewed place, exactly as the canonical join keys require — never inferred,
never produced by a model, and never widened at query time.

Consequences that must be carried into any result measured against it:

* An experiment whose gold derives from this table is measuring whether the
  system **uses the declared bridge correctly**, not whether the bridge is
  right. Those are different claims and only the first is being tested.
* ``basis`` quotes the customer's own description of the edge, from the catalog
  they supplied. The mapping is therefore grounded in *their* statement of what
  the edge means rather than in an assumption about their schema — which is the
  only thing that makes it reviewable by them.
* ``NOT_A_TECHNIQUE`` is as much a part of the declaration as the mapping. An
  edge absent from both tables is an oversight; an edge in ``NOT_A_TECHNIQUE``
  is a decision, with its reason recorded.
"""

from __future__ import annotations

from dataclasses import dataclass

# Which two sources this declaration bridges. Named explicitly, as
# ``CANONICAL_JOIN_KEYS`` names its datasets: a correspondence is between two
# particular schemas and is not transferable. A second customer schema would
# add its own block and its own constants rather than reusing these.
SOURCE_DATASET = "identity"
TARGET_DATASET = "attack"


@dataclass(frozen=True)
class EdgeCorrespondence:
    """One identity edge type and the ATT&CK technique(s) it corresponds to."""

    edge: str
    technique_ids: tuple[str, ...]
    basis: str
    # True when holding this edge is a *component* of the technique rather than
    # the technique itself. The distinction is the customer's, not ours:
    # GET_CHANGES is described as "one half of the DCSync right pair. Alone it
    # is insufficient". Reporting such an edge as the technique outright would
    # assert something their own catalog denies.
    partial: bool = False


# Edges that carry an adversary capability, and the technique that capability is.
IDENTITY_ATTACK_CORRESPONDENCE: tuple[EdgeCorrespondence, ...] = (
    EdgeCorrespondence(
        edge="DC_SYNC",
        technique_ids=("T1003.006",),
        basis=(
            "catalog: 'holds the combination of replication rights that allows "
            "replicating directory secrets from the domain' — that is DCSync"
        ),
    ),
    EdgeCorrespondence(
        edge="GET_CHANGES",
        technique_ids=("T1003.006",),
        basis="catalog: 'One half of the DCSync right pair. Alone it is insufficient'",
        partial=True,
    ),
    EdgeCorrespondence(
        edge="GET_CHANGES_ALL",
        technique_ids=("T1003.006",),
        basis="catalog: 'The second half of the DCSync right pair'",
        partial=True,
    ),
    EdgeCorrespondence(
        edge="GET_CHANGES_IN_FILTERED_SET",
        technique_ids=("T1003.006",),
        basis=(
            "catalog: 'Replication of the filtered attribute set, relevant to "
            "RODC-related escalation' — the same replication primitive, narrower scope"
        ),
        partial=True,
    ),
    EdgeCorrespondence(
        edge="ADD_KEY_CREDENTIAL_LINK",
        technique_ids=("T1649",),
        basis=(
            "catalog: 'allowing a certificate to be attached and the target "
            "impersonated' — forging authentication certificates"
        ),
    ),
    EdgeCorrespondence(
        edge="ALL_EXTENDED_RIGHTS",
        technique_ids=("T1098", "T1003.006"),
        basis=(
            "catalog: 'every extended right on the target, including password "
            "reset and, on a domain, the replication rights' — account "
            "manipulation, and DCSync when the target is a domain"
        ),
    ),
    EdgeCorrespondence(
        edge="GENERIC_ALL",
        technique_ids=("T1098",),
        basis="catalog: 'Full control over the target object. Subsumes every other ACL right'",
    ),
    EdgeCorrespondence(
        edge="GENERIC_WRITE",
        technique_ids=("T1098",),
        basis=(
            "catalog: 'may write any non-protected attribute of the target, "
            "which usually suffices for takeover'"
        ),
    ),
    EdgeCorrespondence(
        edge="WRITE_DACL",
        technique_ids=("T1222.001", "T1098"),
        basis=(
            "catalog: 'may rewrite the target's access control list, and can "
            "therefore grant itself any other right'"
        ),
    ),
    EdgeCorrespondence(
        edge="WRITE_OWNER",
        technique_ids=("T1222.001", "T1098"),
        basis=(
            "catalog: 'may take ownership of the target, and an owner may "
            "rewrite the ACL'"
        ),
    ),
    EdgeCorrespondence(
        edge="OWNS",
        technique_ids=("T1222.001", "T1098"),
        basis=(
            "catalog: 'owns the target object and can therefore rewrite its ACL "
            "at will. Ownership is equivalent to full control'"
        ),
    ),
    EdgeCorrespondence(
        edge="WRITE_ACCOUNT_RESTRICTIONS",
        technique_ids=("T1098",),
        basis=(
            "catalog: 'may write account restriction attributes, enabling "
            "delegation-based escalation'"
        ),
    ),
    EdgeCorrespondence(
        edge="WRITE_GP_LINK",
        technique_ids=("T1484.001",),
        basis=(
            "catalog: 'may change which Group Policy Objects are linked to the "
            "OU, and so what code runs on everything beneath it'"
        ),
    ),
)


# Edges deliberately left unmapped, and why. Each of these describes a state of
# the environment rather than something an adversary does. A trust exists; a
# device runs as an account; a policy is linked. Abusing them is a technique,
# but the edge is not the abuse, and mapping it as though it were would report
# a technique wherever ordinary infrastructure is correctly configured.
NOT_A_TECHNIQUE: dict[str, str] = {
    "APPLIES_FROM": (
        "a Conditional Access policy's scope. Configuration, not an action."
    ),
    "APP_ASSIGNMENT": (
        "a user is entitled to an application. Ordinary provisioning; the "
        "adversary technique would be granting the assignment, not holding it."
    ),
    "BOUND_BY": (
        "a GCP IAM binding grants a role. The binding is the grant, not its abuse."
    ),
    "GP_LINK": (
        "a GPO is linked to a container. Normal policy deployment. WRITE_GP_LINK "
        "-- the ability to CHANGE the link -- is the technique, and is mapped."
    ),
    "MEMBER_OF": (
        "group membership. Adding a member is T1098.007; being a member is how "
        "every directory in the world works, and mapping it would report "
        "Account Manipulation for every user in the tenant."
    ),
    "RUNS_AS": (
        "a host executes under an account. A lateral-movement precondition -- "
        "the catalog says 'compromise of the host yields that account' -- but "
        "the edge records the configuration, not a compromise."
    ),
    "SAME_FOREST_TRUST": (
        "two domains share a forest. The catalog notes this is not a security "
        "boundary; it is still a fact about topology, not an action."
    ),
    "TRUSTED_BY": (
        "a domain trust exists. Modifying one is T1484.002; having one is "
        "ordinary. The schema carries no edge for the modification."
    ),
}


@dataclass(frozen=True)
class CompositeRule:
    """A technique that only exists when several edges are held *together*."""

    requires: tuple[str, ...]
    technique_ids: tuple[str, ...]
    basis: str


# The catalog does not merely say GET_CHANGES is half of something; it says what
# the other half is and what the pair amounts to. Encoding that is the
# difference between reporting DCSync wherever a single replication right exists
# -- which their own text calls insufficient -- and reporting it where the
# combination actually holds.
COMPOSITE_RULES: tuple[CompositeRule, ...] = (
    CompositeRule(
        requires=("GET_CHANGES", "GET_CHANGES_ALL"),
        technique_ids=("T1003.006",),
        basis=(
            "catalog: 'Alone it is insufficient; combined with GET_CHANGES_ALL "
            "it is DCSync'"
        ),
    ),
)


_BY_EDGE: dict[str, EdgeCorrespondence] = {
    entry.edge: entry for entry in IDENTITY_ATTACK_CORRESPONDENCE
}


def correspondence_for(edge: str) -> EdgeCorrespondence | None:
    """The declared correspondence for ``edge``, or None when there is none."""
    return _BY_EDGE.get(str(edge or "").strip().upper())


def technique_ids_for(edges: object) -> tuple[str, ...]:
    """Every declared technique id for ``edges`` (a str or an iterable), deduped.

    Order is the declaration's, then first-seen, so the result is stable and a
    caller can rely on it as a query parameter without sorting away the
    authored priority.
    """
    if isinstance(edges, str):
        names: list[str] = [edges]
    else:
        try:
            names = [str(e) for e in edges]  # type: ignore[union-attr]
        except TypeError:
            return ()
    found: dict[str, None] = {}
    for name in names:
        entry = correspondence_for(name)
        if entry is None:
            continue
        for tid in entry.technique_ids:
            found.setdefault(tid, None)
    return tuple(found)


def produced_technique_ids(edges: object) -> tuple[str, ...]:
    """The techniques a set of edges **actually establishes**, for crossing the bridge.

    Distinct from :func:`technique_ids_for`, and the distinction is the whole
    point. ``technique_ids_for`` answers "what is this edge related to", which is
    the right question for explaining a single edge to a reader. This answers
    "what may be asserted from holding these edges", which is the right question
    for seeding a query against ATT&CK -- and the two differ precisely where the
    catalog says a right is partial.

    A ``partial`` edge contributes nothing on its own: emitting T1003.006 for a
    lone GET_CHANGES would seed ATT&CK with DCSync and produce an answer
    asserting a technique the customer's own description says the edge is
    insufficient for. It contributes only through a :class:`CompositeRule` whose
    requirements are all present.
    """
    if isinstance(edges, str):
        names = [edges]
    else:
        try:
            names = [str(e) for e in edges]  # type: ignore[union-attr]
        except TypeError:
            return ()
    held = {n.strip().upper() for n in names if n}
    found: dict[str, None] = {}
    for name in names:
        entry = correspondence_for(name)
        if entry is None or entry.partial:
            continue
        for tid in entry.technique_ids:
            found.setdefault(tid, None)
    for rule in COMPOSITE_RULES:
        if held.issuperset(rule.requires):
            for tid in rule.technique_ids:
                found.setdefault(tid, None)
    return tuple(found)


def mapped_edges() -> frozenset[str]:
    """Every identity edge type that carries a declared technique."""
    return frozenset(_BY_EDGE)


def declared_edges() -> frozenset[str]:
    """Every edge this file has an opinion about, mapped or explicitly not."""
    return frozenset(_BY_EDGE) | frozenset(NOT_A_TECHNIQUE)
