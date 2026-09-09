#!/usr/bin/env bash
# Install the research-record pre-commit hook.
#
# A plain git hook rather than the `pre-commit` framework: adopting a new tool is
# an explicit non-goal of this retrofit. There is no CI in this repository; this
# hook IS the gate, and `make check-record` runs the same checks by hand.
#
#   ./scripts/install_hooks.sh
#
# Bypass once with `git commit --no-verify`.

set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
hook_dir="$(git rev-parse --git-path hooks)"
hook="${hook_dir}/pre-commit"

mkdir -p "$hook_dir"

cat > "$hook" <<'HOOK'
#!/usr/bin/env bash
# Research-record pre-commit hook. Installed by scripts/install_hooks.sh.
set -euo pipefail

staged=$(git diff --cached --name-only)

# 1. Every commit: a changelog entry that is a changelog entry, not an essay.
if echo "$staged" | grep -q '^docs/changelog.jsonl$'; then
    git show ":docs/changelog.jsonl" | tail -n 5 | python3 -c '
import json, sys
bad = 0
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        entry = json.loads(line)
    except json.JSONDecodeError as exc:
        print(f"[changelog] not JSON: {exc}", file=sys.stderr); bad += 1; continue
    n = len(entry.get("summary", ""))
    if n > 600:
        print(f"[changelog] summary is {n} chars; the limit is 600 — move the detail to "detail" or to a plan/results file", file=sys.stderr); bad += 1
sys.exit(1 if bad else 0)'
fi

# 2. Prose that quotes results must quote current results.
if echo "$staged" | grep -qE '^(README\.md|docs/)'; then
    echo "[research-record] stale-figure scan"
    uv run python scripts/verify_paper_numbers.py --docs --gate --quiet
fi

# The rest only applies when the commit touches the research record.
if ! echo "$staged" | grep -q '^docs/research/'; then
    exit 0
fi

echo "[research-record] regenerating INDEX.md and CURRENT.md"
uv run python scripts/generate_index.py >/dev/null

# If a generated file moved, stage it — a stale index is the single most common
# way this record rots, and failing the commit for a file the hook can fix
# itself would just train people to use --no-verify.
for generated in docs/research/INDEX.md docs/research/CURRENT.md; do
    if ! git diff --quiet -- "$generated"; then
        git add "$generated"
        echo "[research-record] $generated regenerated and staged"
    fi
done

# Validate only the experiment folders this commit touches (`make check-record`
# validates everything). Supersession links are always checked over the whole
# record because a one-way link is a defect in two files.
changed=$(git diff --cached --name-only \
    | grep '^docs/research/experiments/EXP-' \
    | cut -d/ -f1-4 | sort -u || true)

if [ -n "$changed" ]; then
    echo "[research-record] validating: $(echo "$changed" | tr '\n' ' ')"
    # shellcheck disable=SC2086
    uv run python scripts/validate_research.py --skip-index $changed
fi
HOOK

chmod +x "$hook"
echo "Installed ${hook#"$repo_root"/}"
echo "Bypass with: git commit --no-verify"
