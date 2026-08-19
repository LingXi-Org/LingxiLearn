#!/usr/bin/env bash
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

forbidden='(^|/)(\.pytest_cache|\.pytest-tmp[^/]*|\.mypy_cache|\.ruff_cache|__pycache__|\.next|node_modules)(/|$)|(^|/)\.coverage$|\.sqlite3-journal$'
matches="$(git ls-files | grep -E "$forbidden" || true)"

if [[ -n "$matches" ]]; then
  echo "Tracked temporary/build artifacts are forbidden:" >&2
  printf '%s\n' "$matches" >&2
  exit 1
fi

echo "No tracked temporary/build artifacts detected."
