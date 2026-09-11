# POINTERS — EXP-2026-07-011

An audit, not a run. The pointers are to the document, to the script that
derived its counts mechanically, and to the inputs that script reads. Hashes
recomputed 2026-09-09 with `uv run python -m utils.research_record.hashing`
(RESULTS A-1).

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Audit document | `docs/evaluation/2026-07-26/portability.md` | 9656 | sha256:74b9bd58e81f21bf656adefe7973e41ea0f4cb14a47bfc341b54acb9308e3238 | The full three-layer analysis; its Layer-3 table still prints the withdrawn 25/19 |
| Template derivation | `docs/plans/robustness/_overnight/derive_templates.py` | 6853 | sha256:9991aedf2d618fc93d40fcbe8fec6ed8753731a15eb814adde727038ee3ab73c | AST parse. As of `b72eb23` (2026-08-31) it prints 29 distinct / 20 exercised; the version this record originally hashed (5888 bytes, `sha256:04c8acbd…`, at `f87d145`) printed 25/19 |
| Cypher builder | `utils/specialists/cypher/builder.py` | 74949 | sha256:eb9688c0ec56c3a257ced30ca38d4e181d1d645ae56ba742b4d2ec48203371b9 | Input to the derivation — 20 template literals + 1 f-string. **Re-hashed 2026-09-11** after `EXP-2026-09-018` Steps 3, 4 and 4b added the chained route and the filter push-down (was 65540 bytes, `sha256:dbc70b5475…`). Counts re-derived after each: 29 distinct / 20 exercised, unchanged |
| Gremlin builder | `utils/specialists/gremlin/builder.py` | 68257 | sha256:bfd11f06ac0503c4d992697774bb47ade92916f91c6d6f320eb8d98370fa135f | Input to the derivation — 14 template literals. **Re-hashed 2026-09-11** after `EXP-2026-09-018` Steps 1 and 3 changed the anchor namespace and added the chained route (was 57773 bytes, `sha256:5aa4fe01b6e5…`). Counts re-derived after each of Steps 1, 3 and 4: 29 distinct / 20 exercised, unchanged — no repair added a template literal |
| ATT&CK bank | `utils/specialists/tests/golden/attack_questions.json` | 47527 | sha256:c5e3cdc2653bcf2714f7aa41d1eb42daa1b0485a94e36bcffb4a8598ca50408f | `expected_template` values scanned for the exercised count |
| CAPEC bank | `utils/specialists/tests/golden/capec_questions.json` | 31353 | sha256:c8aa4ca6984f8077bf0d5bb7e8d44a0ab3c313e4232c23f4c8d9d78e87f8e4ee | as above |
| Federated bank | `utils/specialists/tests/golden/federated_questions.json` | 74355 | sha256:60dccd52ed100fd7a0cfa66c1dca5fbff052aaa38c9e3ff022f55459ac2b82ab | as above |

The builders and banks are live source files; the hashes pin the state the
29/20 figures were derived from. A later mismatch on those rows means the
counts need re-deriving, not that the record is wrong.
