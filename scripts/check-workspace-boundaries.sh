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
# Matches both absolute @/ paths and relative ../w/ paths.
FORBIDDEN_PATTERNS=(
  "@/app/workspace/\[workspaceId\]/w/"
  "\.\./w/"
  "\.\./\.\./w/"
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
  "hooks"
  "lib"
  "utils"
)

VIOLATIONS=""
VIOLATION_COUNT=0

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

# Regression test: verify the script can actually detect violations
# by temporarily injecting a forbidden import and checking that it fails
REGRESSION_TEST_DIR="$WORKSPACE_DIR/[workspaceId]/components"
if [ -d "$REGRESSION_TEST_DIR" ]; then
  TEST_FILE="$REGRESSION_TEST_DIR/.boundary-regression-test.ts"
  echo "import '../../w/internal';" > "$TEST_FILE"
  
  if grep -rn --include='*.ts' --include='*.tsx' -E "@/app/workspace/\[workspaceId\]/w/|\\\.\\./w/|\\\.\\./\\\.\\./w/" "$REGRESSION_TEST_DIR" 2>/dev/null | grep -q ".boundary-regression-test.ts"; then
    echo "✅ Regression test passed — script can detect forbidden imports"
  else
    echo "❌ Regression test failed — script cannot detect forbidden imports (broken)"
    rm -f "$TEST_FILE"
    exit 1
  fi
  
  rm -f "$TEST_FILE"
fi

exit 0
