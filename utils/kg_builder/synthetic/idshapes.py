#!/usr/bin/env python3
"""Identifier shapes, chosen to make EXP-2026-08-011's H4 a real measurement.

MITRE identifiers are unusually well behaved: ``T1055.011``, ``G0007``,
``CAPEC-66``. Every one collapses to a short scheme under
``idscheme.scheme_of``, so a label learns two or three shapes and the binding
guard has something to guard with. That is the regime in which the 0.7688 →
0.8952 blind rise of EXP-2026-08-005 was measured.

An identity graph is not that regime, and pretending otherwise would make the
experiment answer an easier question than the one asked. Real tenants key
objects by whatever their platform emits:

===============  =========================================  ===============
Shape            Example                                    Learnable?
===============  =========================================  ===============
GUID             ``a3f1c2d4-5e6f-7081-92a3-b4c5d6e7f809``   no — one scheme per value in practice
Windows SID      ``S-1-5-21-1004336348-1177238915-682003330-512``  partly — the prefix is stable
UPN              ``jsmith@corp.example``                    no — free text either side
AWS ARN          ``arn:aws:iam::123456789012:role/Admin``   yes — strong structure
DNS name         ``dc01.corp.example``                      no
Okta id          ``00u1a2b3c4d5e6f7g8h9``                   no — opaque base-62
===============  =========================================  ===============

So the generator mixes them **on purpose**, per label, in roughly the
proportions a real tenant would. H4 predicts more than half of node properties
learn as *open*; that prediction is only meaningful if the data was not built to
satisfy it. The mix here is chosen to look like Active Directory and cloud IAM,
not to hit a number — ARNs are structured because ARNs really are structured,
and GUIDs are opaque because GUIDs really are opaque.

Every function takes an explicit :class:`random.Random` so the whole corpus is
reproducible from one seed.
"""

from __future__ import annotations

import random
import string

_HEX = "0123456789abcdef"
_B62 = string.ascii_letters + string.digits

# A plausible Windows domain SID prefix. Constant across the tenant, as it is in
# a real domain -- which is exactly what makes SIDs *partly* learnable: the
# prefix is stable and only the RID varies.
DOMAIN_SID_PREFIX = "S-1-5-21-1004336348-1177238915-682003330"

# A fixed 12-digit AWS account id, likewise constant per tenant.
AWS_ACCOUNT_ID = "402118836517"

DNS_SUFFIX = "corp.example"


def guid(rng: random.Random) -> str:
    """8-4-4-4-12 hex. Opaque: every value is its own shape."""
    parts = [8, 4, 4, 4, 12]
    return "-".join("".join(rng.choice(_HEX) for _ in range(n)) for n in parts)


def sid(rng: random.Random) -> str:
    """Domain SID with a varying RID. Partly learnable via the stable prefix."""
    return f"{DOMAIN_SID_PREFIX}-{rng.randrange(500, 99999)}"


def upn(rng: random.Random, sam: str) -> str:
    return f"{sam}@{DNS_SUFFIX}"


def arn(rng: random.Random, service: str, resource_type: str, name: str) -> str:
    """A well-formed AWS ARN. Strongly structured, and should learn cleanly."""
    return f"arn:aws:{service}::{AWS_ACCOUNT_ID}:{resource_type}/{name}"


def okta_id(rng: random.Random, prefix: str = "00u") -> str:
    """Okta's opaque base-62 identifier."""
    return prefix + "".join(rng.choice(_B62) for _ in range(17))


def dns_name(rng: random.Random, host: str) -> str:
    return f"{host}.{DNS_SUFFIX}"


def distinguished_name(rng: random.Random, cn: str, ou: str = "Users") -> str:
    dc = ",".join(f"DC={part}" for part in DNS_SUFFIX.split("."))
    return f"CN={cn},OU={ou},{dc}"


def gcp_resource(rng: random.Random, kind: str, name: str) -> str:
    return f"//cloudresourcemanager.googleapis.com/{kind}/{name}"


def entra_object_id(rng: random.Random) -> str:
    """Entra object ids are GUIDs, so this is `guid` under a name that says why."""
    return guid(rng)
