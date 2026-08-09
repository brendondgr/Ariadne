# Author prompt — verbatim

Every one of the 30 questions was written by a **fresh Claude Fable 5 subagent
at high reasoning effort**, one spawn per anchor, with no repository access and
no memory of any other anchor. The template below is
`AUTHOR_PROMPT_TEMPLATE` in `utils/specialists/evalset/holdout_protocol.py`;
the 30 filled prompts follow it verbatim, exactly as sent.

The write-lock of plan 02 §3 is enforced by what these prompts contain. No
repository path, file name, template identifier, example question, or second
entity appears in any of them — `test_holdout_protocol.py` asserts that, so it
is a checked property rather than a claim.

`"author_model": "claude-fable-5 (high effort)"` is recorded in every entry's
`holdout_meta`.

---

## Template

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  {category_description}

about this entity:

  Identifier: {anchor}
  Entity type: {entity_type}
  Name as it appears in the catalogue: {name}

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

---

## The 30 filled prompts, as sent

### H-MIT-01 — `T1543.005` — category `mitigations`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  The mitigations listed for a technique

about this entity:

  Identifier: T1543.005
  Entity type: SubTechnique
  Name as it appears in the catalogue: Container Service

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-DET-01 — `T1098.001` — category `detection`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  How a technique is detected — data components, analytics

about this entity:

  Identifier: T1098.001
  Entity type: SubTechnique
  Name as it appears in the catalogue: Additional Cloud Credentials

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-SW-01 — `T1555.005` — category `software`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  The techniques a piece of software implements

about this entity:

  Identifier: T1555.005
  Entity type: SubTechnique
  Name as it appears in the catalogue: Password Managers

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-LKP-01 — `T1036.010` — category `lookup`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  A plain description of one pattern

about this entity:

  Identifier: T1036.010
  Entity type: SubTechnique
  Name as it appears in the catalogue: Masquerade Account Name

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-GRP-01 — `T1550.002` — category `groups`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  The techniques a named group uses, or the groups using a technique

about this entity:

  Identifier: T1550.002
  Entity type: SubTechnique
  Name as it appears in the catalogue: Pass the Hash

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-SUB-01 — `T1583.003` — category `subtechnique`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  The parent/child relationship around a sub-technique

about this entity:

  Identifier: T1583.003
  Entity type: SubTechnique
  Name as it appears in the catalogue: Virtual Private Server

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-TAC-01 — `T1546.011` — category `tactics`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  The tactics a technique belongs to

about this entity:

  Identifier: T1546.011
  Entity type: SubTechnique
  Name as it appears in the catalogue: Application Shimming

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-MIT-02 — `T1567.004` — category `mitigations`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  The mitigations listed for a technique

about this entity:

  Identifier: T1567.004
  Entity type: SubTechnique
  Name as it appears in the catalogue: Exfiltration Over Webhook

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-DET-02 — `T1027.015` — category `detection`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  How a technique is detected — data components, analytics

about this entity:

  Identifier: T1027.015
  Entity type: SubTechnique
  Name as it appears in the catalogue: Compression

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-SW-02 — `T1005` — category `software`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  The techniques a piece of software implements

about this entity:

  Identifier: T1005
  Entity type: Technique
  Name as it appears in the catalogue: Data from Local System

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-LKP-02 — `T1591.003` — category `lookup`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  A plain description of one pattern

about this entity:

  Identifier: T1591.003
  Entity type: SubTechnique
  Name as it appears in the catalogue: Identify Business Tempo

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-GRP-02 — `T1609` — category `groups`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  The techniques a named group uses, or the groups using a technique

about this entity:

  Identifier: T1609
  Entity type: Technique
  Name as it appears in the catalogue: Container Administration Command

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-MAP-01 — `CAPEC-21` — category `mapping`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  The ATT&CK techniques a pattern maps to

about this entity:

  Identifier: CAPEC-21
  Entity type: AttackPattern
  Name as it appears in the catalogue: Exploitation of Trusted Identifiers

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-EXE-01 — `CAPEC-26` — category `execution`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  The execution steps of a pattern

about this entity:

  Identifier: CAPEC-26
  Entity type: AttackPattern
  Name as it appears in the catalogue: Leveraging Race Conditions

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-CSQ-01 — `CAPEC-671` — category `consequence`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  The consequences a pattern carries

about this entity:

  Identifier: CAPEC-671
  Entity type: AttackPattern
  Name as it appears in the catalogue: Requirements for ASIC Functionality Maliciously Altered

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-CWE-01 — `CAPEC-691` — category `weakness`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  The CWEs a pattern exploits

about this entity:

  Identifier: CAPEC-691
  Entity type: AttackPattern
  Name as it appears in the catalogue: Spoof Open-Source Software Metadata

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-LKP-03 — `CAPEC-321` — category `lookup`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  A plain description of one pattern

about this entity:

  Identifier: CAPEC-321
  Entity type: AttackPattern
  Name as it appears in the catalogue: TCP Sequence Number Probe

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-ABS-01 — `CAPEC-606` — category `hierarchy`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  The abstraction chain — Detailed → Standard → Meta

about this entity:

  Identifier: CAPEC-606
  Entity type: AttackPattern
  Name as it appears in the catalogue: Weakening of Cellular Encryption

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-PRE-01 — `CAPEC-696` — category `prerequisite`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  What a pattern requires

about this entity:

  Identifier: CAPEC-696
  Entity type: AttackPattern
  Name as it appears in the catalogue: Load Value Injection

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-MAP-02 — `CAPEC-639` — category `mapping`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  The ATT&CK techniques a pattern maps to

about this entity:

  Identifier: CAPEC-639
  Entity type: AttackPattern
  Name as it appears in the catalogue: Probe System Files

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-CTM-01 — `CAPEC-603` — category `pattern-to-mitigation`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  From a CAPEC pattern, through its ATT&CK techniques, to mitigations

about this entity:

  Identifier: CAPEC-603
  Entity type: AttackPattern
  Name as it appears in the catalogue: Blockage

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-CTM-02 — `CAPEC-40` — category `pattern-to-mitigation`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  From a CAPEC pattern, through its ATT&CK techniques, to mitigations

about this entity:

  Identifier: CAPEC-40
  Entity type: AttackPattern
  Name as it appears in the catalogue: Manipulating Writeable Terminal Devices

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-CTM-03 — `CAPEC-652` — category `pattern-to-mitigation`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  From a CAPEC pattern, through its ATT&CK techniques, to mitigations

about this entity:

  Identifier: CAPEC-652
  Entity type: AttackPattern
  Name as it appears in the catalogue: Use of Known Kerberos Credentials

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-CTM-04 — `CAPEC-251` — category `pattern-to-mitigation`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  From a CAPEC pattern, through its ATT&CK techniques, to mitigations

about this entity:

  Identifier: CAPEC-251
  Entity type: AttackPattern
  Name as it appears in the catalogue: Local Code Inclusion

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-REV-01 — `T1055.011` — category `reverse-mapping`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  From an ATT&CK technique back to the patterns referencing it

about this entity:

  Identifier: T1055.011
  Entity type: SubTechnique
  Name as it appears in the catalogue: Extra Window Memory Injection

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-REV-02 — `T1552.004` — category `reverse-mapping`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  From an ATT&CK technique back to the patterns referencing it

about this entity:

  Identifier: T1552.004
  Entity type: SubTechnique
  Name as it appears in the catalogue: Private Keys

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-REV-03 — `T1134` — category `reverse-mapping`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  From an ATT&CK technique back to the patterns referencing it

about this entity:

  Identifier: T1134
  Entity type: Technique
  Name as it appears in the catalogue: Access Token Manipulation

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-CHN-01 — `CWE-1243` — category `cwe-chain`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  From a CWE, through patterns, to ATT&CK techniques

about this entity:

  Identifier: CWE-1243
  Entity type: Weakness
  Name as it appears in the catalogue: CWE-1243

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-CHN-02 — `CWE-1316` — category `cwe-chain`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  From a CWE, through patterns, to ATT&CK techniques

about this entity:

  Identifier: CWE-1316
  Entity type: Weakness
  Name as it appears in the catalogue: CWE-1316

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```

### H-CHN-03 — `CWE-270` — category `cwe-chain`

```
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  From a CWE, through patterns, to ATT&CK techniques

about this entity:

  Identifier: CWE-270
  Entity type: Weakness
  Name as it appears in the catalogue: CWE-270

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
```
