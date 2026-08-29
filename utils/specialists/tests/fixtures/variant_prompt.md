# Variant authoring contract

You are writing **paraphrase variants** of golden evaluation questions for a
cybersecurity graph question-answering system. The system answers questions
about MITRE ATT&CK and CAPEC by matching the words in a question against the
node labels and relationship types its databases declare.

Your variants are the test of whether that matching survives ordinary English.

## The one rule that overrides everything

**A variant must have the same correct answer as the gold question.** You are
rephrasing the question, never changing it. If the gold question asks for the
mitigations of T1176, every variant must still be asking for the mitigations of
T1176 — not its detections, not its sub-techniques, not "tell me about it".

A variant whose correct answer differs from the gold question's is worse than no
variant at all, because it will be scored as a system failure when it is
actually an authoring failure.

## Tiers

Write **one variant per tier** for each question, T1 through T5, plus T6 only
where asked. Each tier removes one more crutch.

| Tier | Keeps | Removes | Example against *"What are the mitigations for T1176?"* |
|---|---|---|---|
| **T1** | the identifier | the schema's word | "How do I defend against T1176?" |
| **T2** | the identifier | the sentence shape | "T1176 — what stops it?" |
| **T3** | the entity's **exact name** | the identifier | "What are the mitigations for Software Extensions?" |
| **T4** | the *idea* of the name | the identifier and the exact name | "What countermeasures exist for malicious browser add-ons?" |
| **T5** | only the description | identifier, name, and schema words | "How do I stop attackers from setting up persistence through browser extensions?" |
| **T6** | nothing — a **negative control** | — | "What are the mitigations for the Belgian Waffle attack technique?" |

**T1 and T2 must contain the identifier.** They test vocabulary matching only.

**T3 must contain the anchor's exact name**, spelled exactly as given to you in
`anchor_names`. It must not contain the identifier.

**T4** paraphrases that name. No identifier, no exact name, and no word from the
`avoid` list.

**T5** describes the entity so a security analyst would recognise it, using
neither its identifier, nor its name, nor any word from `avoid`. This is the
hardest tier and the most valuable one. Use the `description` in `anchor_names`
as your source material — rewrite it, do not quote it.

**T6** is a plausible, well-formed question about something that **does not
exist** in these catalogues. Invent a convincing technique or pattern name. The
correct answer is *nothing*, and a system that answers it confidently has
failed. Write T6 only for the questions the batch marks `needs_negative`.

## The avoid list

Every question carries an `avoid` array: the words appearing in its databases'
node labels and relationship types. **T4 and T5 must contain none of them**,
in singular or plural form.

This is enforced mechanically after you finish. If you write "what mitigates
browser extensions" as a T5, it is rejected, because `mitigates` is a
relationship name. Reach for the analyst's phrasing instead — *stop*, *prevent*,
*block*, *harden against*, *defend against*.

## Questions with no anchor name

Some questions have an empty `anchor_names` — they ask about entities that do
not exist, or they are bounded scans over a whole label. For those, write **T1
and T2 only**, and skip T3 through T5. Do not invent a name.

## Output

Return **only** a JSON array, no prose around it, no markdown fence:

```
[
  {"case_id": "A-MIT-01", "tier": "T1", "question": "...", "note": "verb swapped"},
  {"case_id": "A-MIT-01", "tier": "T2", "question": "...", "note": "..."}
]
```

`note` is one short clause saying what you changed. Keep every question a single
sentence, natural, and something a working security analyst would plausibly
type.
