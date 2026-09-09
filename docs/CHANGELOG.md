# Changelog

The change history is [`changelog.jsonl`](changelog.jsonl): one JSON object per
line, oldest first, one entry per change, never rewritten. This page only
explains how to read and extend it.

## Two schemas

| Entries | Shape | Period |
|---|---|---|
| 1 – ~450 | `{"timestamp": ISO-8601, "summary": …, "why": …}` | 11 June – 20 August 2026 |
| ~450 – present | `{"date": YYYY-MM-DD, "kind": …, "summary": …, "detail": …, "files": […], "tests": …}` | 20 August 2026 onward |

Both are valid. `kind` is one of `experiment`, `fix`, `feature`, `plan`,
`docs`, `tooling`, `research`, `code`, `protocol`, `report`, `dataset`,
`decision`, `test`, `refactor`, `correction`.

## Writing an entry

Append one line. `summary` is two to four sentences: what changed and why. Put
anything longer in `detail`. The pre-commit hook rejects a `summary` over 600
characters — history is in git, and a changelog entry that needs a page is a
plan or a results file, not a changelog entry.

```json
{"date": "2026-09-09", "kind": "docs", "summary": "What changed. Why.", "files": ["docs/x.md"], "tests": "make validate-research"}
```

Read the last twenty lines before starting work; it is the fastest way to learn
what moved recently:

```bash
tail -n 20 docs/changelog.jsonl | python3 -c 'import sys,json; [print(json.loads(l).get("date") or json.loads(l)["timestamp"][:10], "-", json.loads(l)["summary"][:160]) for l in sys.stdin]'
```
