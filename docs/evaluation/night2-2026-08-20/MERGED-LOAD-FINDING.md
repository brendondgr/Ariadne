# The merged load stopped on a decision, not a bug

`N6` failed, and the failure is worth more than the phase would have been.

## What happened

ATT&CK loaded into the isolated merged store cleanly. CAPEC's **nodes** loaded.
CAPEC's **relationships** did not:

```
ValueError: Unsafe Neo4j relationship type: 'CanAlsoBe'
```

The merged store is therefore in a **partial state and must not be queried**:

| | |
|---|---:|
| nodes | 9138 |
| …from ATT&CK | 4369 |
| …from CAPEC | 4769 |
| entities carrying no source marker | 0 |
| relationships | 27669 — **all ATT&CK's; CAPEC contributed none** |

The main ATT&CK store was counted before and after every load and did not move.
That guard was the point of writing it.

## Why it happened

`utils/graph_loader/stores/neo4j.py:15` admits relationship types matching
`^[A-Z][A-Z0-9_]*$` — screaming snake case. Ten of CAPEC's sixteen relationship
types are names this repo's own loader invented and they comply. The other six
come straight from the `Nature` attribute of the CAPEC XML and are CamelCase:

    CanAlsoBe   CanFollow   CanPrecede   ChildOf   ParentOf   PeerOf

CAPEC has only ever been loaded into Gremlin, where no such rule exists, so this
has never fired before. Note the asymmetry one line above: `_SAFE_LABEL` already
admits `^[A-Za-z][A-Za-z0-9_]*$`. Labels may be CamelCase; relationships may not.

**This invalidates a premise of the plan.** Step 5 assumed "the loaders are
already dataset-agnostic and additive — running the ATT&CK load and then the
CAPEC load into the same database already produces a merged graph, with no code
change". That is true of ATT&CK into Neo4j and false of CAPEC into Neo4j.

## Why it was not fixed unattended

Both repairs are small and they are not equivalent, and the choice is a design
judgment on a function whose name is about safety:

**A — widen the relationship rule to match the label rule.** One character class.
The regex is what stops backticks, spaces and injection; case has nothing to do
with that, and the label rule already sets the precedent. Cheapest, and the
merged graph then names relationships exactly as the CAPEC source does.

**B — normalise CAPEC's six names to `CAN_ALSO_BE`, `CHILD_OF`, and so on.**
Leaves the safety rule untouched and gives the merged graph one naming
convention. But it makes the merged store name its relationships differently
from the Gremlin store holding the same data, so a query written against one
does not port to the other — and the federated-versus-merged comparison is
precisely about queries porting between stores.

B quietly disadvantages the merged arm in the comparison it exists to inform.
A does not, at the cost of touching a validator. That is the operator's call.

Whichever is chosen, the merged store must be wiped and reloaded from empty —
the current contents are half a catalogue.
