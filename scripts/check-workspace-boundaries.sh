#!/usr/bin/env bash
#
# check-workspace-boundaries.sh
#
# Enforces that product resource pages (files/, knowledge/, tables/, home/,
# settings/, logs/) and shared workspace components/ do NOT import from the
# workflow editor's private directory (w/**).
#
# Only files inside w/ itself may reference w/ internal modules.
#
# Exit 0 = clean, Exit 1 = violations found.

set -euo pipefail

WEB_DIR="${1:-web}"
WORKSPACE_DIR="$WEB_DIR/app/workspace"

if [ ! -d "$WORKSPACE_DIR" ]; then
  echo "⚠  workspace directory not found at $WORKSPACE_DIR — skipping boundary check"
  exit 0
fi

# Patterns that indicate an import from the workflow editor's private directory.
# Matches the absolute @/ alias, relative paths at ANY depth ((\.\./)+w/ is one
# or more "../" hops followed by w/, so ../../../w/ and deeper can never slip
# past the gate), and relative paths that traverse the workspace tree down to
# w/ from web-level directories such as lib/ or hooks/ (../../app/workspace/
# [workspaceId]/w/...). Each violation is reported exactly once.
FORBIDDEN_PATTERNS=(
  "@/app/workspace/\[workspaceId\]/w/"
  "(\.\./)+w/"
  "(\.\./)+app/workspace/\[workspaceId\]/w/"
)

# Directories that are product pages or shared layers (must NOT import from w/).
PRODUCT_DIRS=(
  "files"
  "knowledge"
  "tables"
  "home"
  "settings"
  "logs"
  "components"
  "chat"
  "skills"
  "integrations"
  "providers"
  "utils"
)

# Special handling for lib and hooks - they exist at web/ level, not under [workspaceId]
SPECIAL_DIRS=(
  "lib"
  "hooks"
)

VIOLATIONS=""
VIOLATION_COUNT=0

# Check workspace-specific product directories
for dir in "${PRODUCT_DIRS[@]}"; do
  target="$WORKSPACE_DIR/[workspaceId]/$dir"
  if [ ! -d "$target" ]; then
    continue
  fi

  for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
    while IFS= read -r line; do
      if [ -n "$line" ]; then
        VIOLATIONS="$VIOLATIONS$line"$'\n'
        VIOLATION_COUNT=$((VIOLATION_COUNT + 1))
      fi
    done < <(grep -rn --include='*.ts' --include='*.tsx' -E "$pattern" "$target" 2>/dev/null | grep -v "node_modules" || true)
  done
done

# Check web-level directories (lib, hooks) that must not import from w/**
for dir in "${SPECIAL_DIRS[@]}"; do
  target="$WEB_DIR/$dir"
  if [ ! -d "$target" ]; then
    continue
  fi

  for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
    while IFS= read -r line; do
      if [ -n "$line" ]; then
        VIOLATIONS="$VIOLATIONS$line"$'\n'
        VIOLATION_COUNT=$((VIOLATION_COUNT + 1))
      fi
    done < <(grep -rn --include='*.ts' --include='*.tsx' -E "$pattern" "$target" 2>/dev/null | grep -v "node_modules" || true)
  done
done

if [ $VIOLATION_COUNT -gt 0 ]; then
  echo "❌ Architecture boundary violation ($VIOLATION_COUNT imports from w/**):"
  echo ""
  echo "Product pages and shared components must NOT import from the workflow"
  echo "editor's private directory (w/**). Extract shared primitives to"
  echo "components/ instead."
  echo ""
  echo "$VIOLATIONS"
  exit 1
fi

echo "✅ Workspace boundary check passed — no product page imports from w/**"
exit 0
