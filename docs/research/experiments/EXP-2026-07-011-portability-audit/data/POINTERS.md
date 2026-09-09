# POINTERS — EXP-2026-07-011

An audit, not a run. The pointers are to the document, to the script that
derived its counts mechanically, and to the inputs that script reads. Hashes
recomputed 2026-09-09 with `uv run python -m utils.research_record.hashing`
(RESULTS A-1).

| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |
|---|---|---|---|---|
| Audit document | `docs/evaluation/2026-07-26/portability.md` | 9656 | sha256:74b9bd58e81f21bf656adefe7973e41ea0f4cb14a47bfc341b54acb9308e3238 | The full three-layer analysis; its Layer-3 table still prints the withdrawn 25/19 |
| Template derivation | `docs/plans/robustness/_overnight/derive_templates.py` | 6853 | sha256:9991aedf2d618fc93d40fcbe8fec6ed8753731a15eb814adde727038ee3ab73c | AST parse. As of `b72eb23` (2026-08-31) it prints 29 distinct / 20 exercised; the version this record originally hashed (5888 bytes, `sha256:04c8acbd…`, at `f87d145`) printed 25/19 |
| Cypher builder | `utils/specialists/cypher/builder.py` | 65540 | sha256:dbc70b54756da67158865d42f49b11c3f7590c7d56cb64749a1a67ca5239db9d | Input to the derivation — 20 template literals + 1 f-string, as hashed 2026-09-09 |
| Gremlin builder | `utils/specialists/gremlin/builder.py` | 57773 | sha256:5aa4fe01b6e530331ef2299e5081bab265e464663efb0511b6c2cc1929c0e38a | Input to the derivation — 14 template literals, as hashed 2026-09-09 |
| ATT&CK bank | `utils/specialists/tests/golden/attack_questions.json` | 47527 | sha256:c5e3cdc2653bcf2714f7aa41d1eb42daa1b0485a94e36bcffb4a8598ca50408f | `expected_template` values scanned for the exercised count |
| CAPEC bank | `utils/specialists/tests/golden/capec_questions.json` | 31353 | sha256:c8aa4ca6984f8077bf0d5bb7e8d44a0ab3c313e4232c23f4c8d9d78e87f8e4ee | as above |
| Federated bank | `utils/specialists/tests/golden/federated_questions.json` | 74355 | sha256:60dccd52ed100fd7a0cfa66c1dca5fbff052aaa38c9e3ff022f55459ac2b82ab | as above |

The builders and banks are live source files; the hashes pin the state the
29/20 figures were derived from. A later mismatch on those rows means the
counts need re-deriving, not that the record is wrong.
