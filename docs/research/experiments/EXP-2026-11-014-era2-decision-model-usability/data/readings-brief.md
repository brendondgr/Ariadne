# Brief: plain readings for graph relations

You are writing one short reading for each relation below. A reading tells a person which
related things they get if they follow that relation from a known entity.

Each key is `dataset|Label|RELATION|direction|TargetLabel`:
- `out` means Label -RELATION-> TargetLabel; `in` means TargetLabel -RELATION-> Label.
- The known entity is always the `Label`. The reading names what you reach: the `TargetLabel` things.

Rules for each reading:
1. A noun phrase from the known entity's point of view, for example "the sub-techniques this
   software uses" or "the groups that use this software".
2. At most 12 words. Plain English: no CamelCase or ALL_CAPS schema names, no arrows.
3. Get the direction right: `in` and `out` of the same relation read differently.
4. Every reading for the same dataset and Label must differ from the others, so a reader can
   tell any two apart.
5. Use the descriptions below for meaning. Do not invent facts beyond them.

Return one JSON object mapping every key to its reading, and nothing else.

## Dataset `attack`

### Node types

- `Analytic`: A platform-specific detection analytic (AN-ID) that implements part of a DetectionStrategy by monitoring DataComponent log sources.
- `Campaign`: A named series of intrusion activity attributed to a Group (C-ID).
- `DataComponent`: A specific observable within a data source used for detection.
- `DetectionStrategy`: A named v19 detection strategy (DET-ID) that detects one or more Techniques.
- `Group`: A tracked threat actor or intrusion set (G-ID).
- `Matrix`: The top-level ATT&CK matrix for a domain (e.g., Enterprise) that organizes tactics and techniques.
- `Mitigation`: A defensive measure that reduces technique risk (M-ID).
- `Software`: A tool, malware, or utility used in attacks (S-ID).
- `SubTechnique`: A more specific variant of a parent Technique (T-ID.NNN).
- `Tactic`: A high-level adversary goal (TA-ID) such as Persistence or Exfiltration.
- `Technique`: An adversary action or behavior at the atomic level (T-ID); may have sub-techniques.

### Relations

- `ATTRIBUTED_TO`: A Campaign is attributed to a Group.
- `DETECTS`: A DetectionStrategy detects a Technique or SubTechnique.
- `HAS_ANALYTIC`: A DetectionStrategy is implemented by an Analytic (DetectionStrategy -> Analytic, from x_mitre_analytic_refs).
- `HAS_SUBTECHNIQUE`: A Technique contains a SubTechnique.
- `HAS_TACTIC`: The Matrix organizes a Tactic (Matrix -> Tactic, from x-mitre-matrix.tactic_refs).
- `HAS_TECHNIQUE`: A Tactic contains a Technique.
- `MITIGATES`: A Mitigation reduces risk for a Technique.
- `MONITORS`: An Analytic monitors a DataComponent's log sources (Analytic -> DataComponent, from x_mitre_log_source_references).
- `USES`: A Group or Software uses a Technique/SubTechnique; a Technique uses Software.

### Keys to write

- `attack|Analytic|HAS_ANALYTIC|in|DetectionStrategy`
- `attack|Analytic|MONITORS|out|DataComponent`
- `attack|Campaign|ATTRIBUTED_TO|out|Group`
- `attack|Campaign|USES|out|Software`
- `attack|Campaign|USES|out|SubTechnique`
- `attack|Campaign|USES|out|Technique`
- `attack|DataComponent|MONITORS|in|Analytic`
- `attack|DetectionStrategy|DETECTS|out|SubTechnique`
- `attack|DetectionStrategy|DETECTS|out|Technique`
- `attack|DetectionStrategy|HAS_ANALYTIC|out|Analytic`
- `attack|Group|ATTRIBUTED_TO|in|Campaign`
- `attack|Group|USES|out|Software`
- `attack|Group|USES|out|SubTechnique`
- `attack|Group|USES|out|Technique`
- `attack|Matrix|HAS_TACTIC|out|Tactic`
- `attack|Software|USES|in|Campaign`
- `attack|Software|USES|in|Group`
- `attack|Software|USES|out|SubTechnique`
- `attack|Software|USES|out|Technique`
- `attack|SubTechnique|DETECTS|in|DetectionStrategy`
- `attack|SubTechnique|HAS_SUBTECHNIQUE|in|Technique`
- `attack|SubTechnique|HAS_TECHNIQUE|in|Tactic`
- `attack|SubTechnique|MITIGATES|in|Mitigation`
- `attack|SubTechnique|USES|in|Campaign`
- `attack|SubTechnique|USES|in|Group`
- `attack|SubTechnique|USES|in|Software`
- `attack|Tactic|HAS_TACTIC|in|Matrix`
- `attack|Tactic|HAS_TECHNIQUE|out|SubTechnique`
- `attack|Tactic|HAS_TECHNIQUE|out|Technique`
- `attack|Technique|DETECTS|in|DetectionStrategy`
- `attack|Technique|HAS_SUBTECHNIQUE|out|SubTechnique`
- `attack|Technique|HAS_TECHNIQUE|in|Tactic`
- `attack|Technique|MITIGATES|in|Mitigation`
- `attack|Technique|USES|in|Campaign`
- `attack|Technique|USES|in|Group`
- `attack|Technique|USES|in|Software`

## Dataset `capec`

### Node types

- `AlternateTerm`: Another name the attack pattern is known by (CAPEC Alternate_Terms), with an optional explanatory description.
- `AttackPattern`: A CAPEC attack pattern (CAPEC-ID) describing an adversarial technique at an abstract level.
- `Category`: A grouping of related attack patterns sharing a common attribute or theme.
- `Consequence`: A security impact or outcome that results from a successful attack pattern.
- `Example`: A concrete real-world instance illustrating the attack pattern (CAPEC Example_Instances). Prose, one node per declared example.
- `ExecutionStep`: A discrete numbered step in an attack pattern's execution flow.
- `ExternalReference`: A published resource (paper, CVE, URL) referenced by a CAPEC entry.
- `Indicator`: An observable sign that the attack pattern is being attempted or has succeeded (CAPEC Indicators). Prose, one node per declared indicator.
- `Mitigation`: A countermeasure or defensive recommendation for an attack pattern.
- `Prerequisite`: A condition that must hold before the attack pattern can be attempted (CAPEC Prerequisites). Prose, one node per declared prerequisite.
- `Resource`: A capability, tool or access an attacker must have to attempt the pattern (CAPEC Resources_Required). Prose, one node per declared resource.
- `Skill`: A required attacker capability (e.g., low/medium/high skill level) for executing an attack pattern.
- `TaxonomyEntry`: A mapping between a CAPEC attack pattern and an external taxonomy (e.g., ATT&CK, WASC).
- `View`: A curated subset or perspective over the CAPEC catalog (e.g., WASC, OWASP).
- `Weakness`: A CWE software weakness exploited by one or more attack patterns.

### Relations

- `CanAlsoBe`: An AttackPattern can also be characterized as another AttackPattern.
- `CanFollow`: An AttackPattern can occur after another in an attack chain.
- `CanPrecede`: An AttackPattern can occur before another in an attack chain.
- `ChildOf`: An AttackPattern is a more specific variant of a parent AttackPattern.
- `EXPLOITS_WEAKNESS`: An AttackPattern exploits a specific CWE Weakness.
- `HAS_ALTERNATE_TERM`: Attack pattern -> another name it is known by.
- `HAS_CONSEQUENCE`: An AttackPattern leads to a Consequence if successful.
- `HAS_EXAMPLE`: Attack pattern -> a real-world instance illustrating it.
- `HAS_EXECUTION_STEP`: An AttackPattern contains an ordered ExecutionStep.
- `HAS_INDICATOR`: Attack pattern -> an observable sign that it is being attempted.
- `HAS_MITIGATION`: An AttackPattern is addressed by a Mitigation.
- `HAS_PREREQUISITE`: Attack pattern -> a condition that must hold before it can be attempted.
- `HAS_REFERENCE`: An AttackPattern, Category, or View is documented by an ExternalReference.
- `IN_VIEW`: An AttackPattern or Category appears in a View.
- `MAPS_TO`: An AttackPattern maps to an entry in an external taxonomy (TaxonomyEntry).
- `MEMBER_OF`: An AttackPattern is a member of a Category.
- `NEXT_STEP`: One ExecutionStep is followed by another in sequence.
- `ParentOf`: An AttackPattern is the parent of a more specific child AttackPattern.
- `PeerOf`: Two AttackPatterns are related alternatives at the same abstraction level.
- `REQUIRES_RESOURCE`: Attack pattern -> a capability or access the attacker must have.
- `REQUIRES_SKILL`: An AttackPattern requires an attacker to possess a Skill.

### Keys to write

- `capec|AttackPattern|CanAlsoBe|in|AttackPattern`
- `capec|AttackPattern|CanAlsoBe|out|AttackPattern`
- `capec|AttackPattern|CanFollow|in|AttackPattern`
- `capec|AttackPattern|CanFollow|out|AttackPattern`
- `capec|AttackPattern|CanPrecede|in|AttackPattern`
- `capec|AttackPattern|CanPrecede|out|AttackPattern`
- `capec|AttackPattern|ChildOf|in|AttackPattern`
- `capec|AttackPattern|ChildOf|out|AttackPattern`
- `capec|AttackPattern|EXPLOITS_WEAKNESS|out|Weakness`
- `capec|AttackPattern|HAS_ALTERNATE_TERM|out|AlternateTerm`
- `capec|AttackPattern|HAS_CONSEQUENCE|out|Consequence`
- `capec|AttackPattern|HAS_EXAMPLE|out|Example`
- `capec|AttackPattern|HAS_EXECUTION_STEP|out|ExecutionStep`
- `capec|AttackPattern|HAS_INDICATOR|out|Indicator`
- `capec|AttackPattern|HAS_MITIGATION|out|Mitigation`
- `capec|AttackPattern|HAS_PREREQUISITE|out|Prerequisite`
- `capec|AttackPattern|HAS_REFERENCE|out|ExternalReference`
- `capec|AttackPattern|IN_VIEW|out|View`
- `capec|AttackPattern|MAPS_TO|out|TaxonomyEntry`
- `capec|AttackPattern|MEMBER_OF|out|Category`
- `capec|AttackPattern|PeerOf|in|AttackPattern`
- `capec|AttackPattern|PeerOf|out|AttackPattern`
- `capec|AttackPattern|REQUIRES_RESOURCE|out|Resource`
- `capec|AttackPattern|REQUIRES_SKILL|out|Skill`
- `capec|Category|IN_VIEW|out|View`
- `capec|Category|MEMBER_OF|in|AttackPattern`
- `capec|Weakness|EXPLOITS_WEAKNESS|in|AttackPattern`
