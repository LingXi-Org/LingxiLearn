#!/usr/bin/env bash
#
# test-workspace-boundaries.sh
#
# Repeatable fixture test for check-workspace-boundaries.sh. Builds synthetic
# web/ trees in a temp directory (never inside the repo — fixtures that live in
# the real tree would be flagged by the checker itself) and asserts:
#
#   1. a clean tree (allowed absolute/relative imports, plus a w/ internal
#      self-reference) passes with exit 0;
#   2. every forbidden import form — the @/ absolute alias, ../w/ at any
#      relative depth, and relative paths that reach w/ through
#      app/workspace/[workspaceId]/ from web-level directories — makes the
#      checker exit 1 and name the offending file.
#
# Exit 0 = all assertions passed, exit 1 = at least one failed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECKER="$SCRIPT_DIR/check-workspace-boundaries.sh"

FAILURES=0

note() { echo "  $*"; }
fail() { echo "  ❌ $*"; FAILURES=$((FAILURES + 1)); }

# create_tree <root> — minimal web/ skeleton covering both scanned dir kinds.
create_tree() {
  local root="$1"
  mkdir -p \
    "$root/web/app/workspace/[workspaceId]/files/nested/deep" \
    "$root/web/app/workspace/[workspaceId]/home" \
    "$root/web/app/workspace/[workspaceId]/w/components/sidebar" \
    "$root/web/hooks" \
    "$root/web/lib/search"
}

# ---------------------------------------------------------------------------
# Case 1: a clean tree must pass.
# ---------------------------------------------------------------------------
echo "case 1: allowed imports pass"

CLEAN_ROOT="$(mktemp -d)"
create_tree "$CLEAN_ROOT"

cat > "$CLEAN_ROOT/web/app/workspace/[workspaceId]/home/ok-absolute.ts" <<'EOF'
import { ContextMenu } from "@/components/context-menu"
import { fuzzyMatch } from "@/lib/search/fuzzy-match"
EOF
cat > "$CLEAN_ROOT/web/app/workspace/[workspaceId]/files/nested/ok-relative.ts" <<'EOF'
import { thing } from "../components/thing"
import { shared } from "../../shared/util"
EOF
# Files inside w/ may reference w/ internals; the checker never scans w/.
cat > "$CLEAN_ROOT/web/app/workspace/[workspaceId]/w/components/sidebar/self.ts" <<'EOF'
import { peer } from "@/app/workspace/[workspaceId]/w/components/sidebar/peer"
import { cousin } from "../../w/components/cousin"
EOF
cat > "$CLEAN_ROOT/web/lib/search/ok-lib.ts" <<'EOF'
import { fuzzyMatch } from "@/lib/search/fuzzy-match"
import { local } from "./local"
EOF

if bash "$CHECKER" "$CLEAN_ROOT/web" > "$CLEAN_ROOT/out.log" 2>&1; then
  note "clean tree accepted"
else
  fail "clean tree was rejected:"
  cat "$CLEAN_ROOT/out.log"
fi
rm -rf "$CLEAN_ROOT"

# ---------------------------------------------------------------------------
# Case 2: every forbidden form must be caught and named.
# ---------------------------------------------------------------------------
echo "case 2: forbidden imports at any depth are caught"

BAD_ROOT="$(mktemp -d)"
create_tree "$BAD_ROOT"

cat > "$BAD_ROOT/web/app/workspace/[workspaceId]/home/violation-alias.ts" <<'EOF'
import { x } from "@/app/workspace/[workspaceId]/w/components/sidebar/x"
EOF
cat > "$BAD_ROOT/web/app/workspace/[workspaceId]/files/violation-depth-1.ts" <<'EOF'
import { x } from "../w/components/sidebar/x"
EOF
cat > "$BAD_ROOT/web/app/workspace/[workspaceId]/files/nested/violation-depth-2.ts" <<'EOF'
import { x } from "../../w/components/sidebar/x"
EOF
cat > "$BAD_ROOT/web/app/workspace/[workspaceId]/files/nested/deep/violation-depth-3.ts" <<'EOF'
import { x } from "../../../w/components/sidebar/x"
EOF
cat > "$BAD_ROOT/web/app/workspace/[workspaceId]/files/nested/deep/violation-depth-4.ts" <<'EOF'
import { x } from "../../../../w/components/sidebar/x"
EOF
cat > "$BAD_ROOT/web/lib/search/violation-lib.ts" <<'EOF'
import { x } from "@/app/workspace/[workspaceId]/w/components/sidebar/x"
EOF
cat > "$BAD_ROOT/web/lib/search/violation-lib-relative.ts" <<'EOF'
import { x } from "../../app/workspace/[workspaceId]/w/components/sidebar/x"
EOF
cat > "$BAD_ROOT/web/hooks/violation-hooks-relative.ts" <<'EOF'
import { x } from "../app/workspace/[workspaceId]/w/components/sidebar/x"
EOF

EXPECTED_FILES=(
  violation-alias.ts
  violation-depth-1.ts
  violation-depth-2.ts
  violation-depth-3.ts
  violation-depth-4.ts
  violation-lib.ts
  violation-lib-relative.ts
  violation-hooks-relative.ts
)

if bash "$CHECKER" "$BAD_ROOT/web" > "$BAD_ROOT/out.log" 2>&1; then
  fail "checker accepted a tree full of w/** imports"
else
  note "violating tree rejected"
fi
for name in "${EXPECTED_FILES[@]}"; do
  if grep -q "$name" "$BAD_ROOT/out.log"; then
    note "$name reported"
  else
    fail "$name was NOT reported by the checker"
  fi
done
rm -rf "$BAD_ROOT"

if [ "$FAILURES" -gt 0 ]; then
  echo "❌ boundary checker fixture test failed ($FAILURES assertion(s))"
  exit 1
fi

echo "✅ boundary checker fixture test passed"
exit 0
