#!/usr/bin/env bash
# Install the research-record pre-commit hook.
#
# A plain git hook rather than the `pre-commit` framework: adopting a new tool is
# an explicit non-goal of this retrofit, and the hook only needs to do two cheap
# things. CI (.github/workflows/research-record.yml) is the real gate; this hook
# just makes the CI failure rare.
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

# Only do work when the commit actually touches the research record.
if ! git diff --cached --name-only | grep -q '^docs/research/'; then
    exit 0
fi

echo "[research-record] regenerating INDEX.md"
uv run python scripts/generate_index.py >/dev/null

# If the index moved, stage it — a stale index is the single most common way
# this record rots, and failing the commit for a file the hook can fix itself
# would just train people to use --no-verify.
if ! git diff --quiet -- docs/research/INDEX.md; then
    git add docs/research/INDEX.md
    echo "[research-record] INDEX.md regenerated and staged"
fi

# Validate only the experiment folders this commit touches. Full validation and
# the figure check run in CI.
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
