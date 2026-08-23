/**
 * Auth boundary check: ensures Better Auth never re-enters the LingxiLearn
 * production codebase. LingxiLearn delegates all credential, OIDC token and
 * session ownership to the LingxiIdentity BFF (issue #52).
 *
 * The check parses import/require/dynamic-import specifiers from every
 * production source file (all TS/JS under the web root except tooling and
 * generated directories) and rejects:
 *
 *   - `better-auth` and `better-auth/*` (server or client runtime)
 *   - `@better-auth/*` (plugins, adapters, helpers)
 *   - `@sim/auth` and `@sim/auth/*` (the deleted Sim auth compatibility
 *     package; its pure Principal type contract now lives at
 *     `@/lib/auth/principal`, which is a plain app module and is allowed)
 *
 * No exception is kept for any `@sim/auth` entry point so the compatibility
 * package cannot be reintroduced to host a second auth runtime.
 *
 * Lockfiles, package manifests and documentation are never scanned — only
 * import statements in code count as production dependencies.
 */

import { lstatSync, readdirSync, readFileSync } from 'node:fs'
import { join, relative, resolve, sep } from 'node:path'

const WEB_ROOT = resolve(import.meta.dirname, '..')

/**
 * Directories deliberately excluded from the scan:
 *   - node_modules/.next/.turbo/dist/build/coverage/.cache: generated or third-party
 *   - .git/.github/.husky: repository metadata, not application code
 *   - scripts: development tooling (this checker lives here)
 *   - var/public/docker: runtime data, static assets and ops configuration
 */
const SKIP_DIRS = new Set([
  'node_modules',
  '.next',
  '.turbo',
  '.venv',
  '.pytest_cache',
  '.git',
  '.github',
  '.husky',
  'scripts',
  'var',
  'public',
  'docker',
  'coverage',
  'dist',
  'build',
  '.cache',
])

const CODE_EXTENSION = /\.(ts|tsx|js|jsx|mjs|cjs)$/

/** Returns the violated boundary name for a module specifier, or null when allowed. */
function forbiddenBoundary(specifier: string): string | null {
  if (specifier === 'better-auth' || specifier.startsWith('better-auth/')) {
    return 'better-auth'
  }
  if (specifier.startsWith('@better-auth/')) {
    return '@better-auth/*'
  }
  const isSimAuth = specifier === '@sim/auth' || specifier.startsWith('@sim/auth/')
  if (isSimAuth) {
    return '@sim/auth (package deleted; principal contract lives at @/lib/auth/principal)'
  }
  return null
}

const SPECIFIER_PATTERNS: RegExp[] = [
  // import … from 'x' / export … from 'x' (covers `import type`)
  /\bfrom\s*['"]([^'"]+)['"]/g,
  // side-effect import 'x'
  /\bimport\s*['"]([^'"]+)['"]/g,
  // require('x') and dynamic import('x')
  /\b(?:require|import)\s*\(\s*['"]([^'"]+)['"]\s*\)/g,
]

interface Violation {
  file: string
  line: number
  specifier: string
  boundary: string
}

function scanFile(absolutePath: string): Violation[] {
  const content = readFileSync(absolutePath, 'utf8')
  const violations: Violation[] = []
  const seen = new Set<string>()

  for (const pattern of SPECIFIER_PATTERNS) {
    pattern.lastIndex = 0
    let match = pattern.exec(content)
    while (match !== null) {
      const specifier = match[1]
      const boundary = forbiddenBoundary(specifier)

      if (boundary) {
        const line = content.slice(0, match.index).split('\n').length
        const key = `${line}:${specifier}`
        if (!seen.has(key)) {
          seen.add(key)
          violations.push({
            file: relative(WEB_ROOT, absolutePath).split(sep).join('/'),
            line,
            specifier,
            boundary,
          })
        }
      }

      match = pattern.exec(content)
    }
  }

  return violations
}

function* walkCodeFiles(dir: string): Generator<string> {
  let entries: string[]
  try {
    entries = readdirSync(dir)
  } catch {
    return
  }
  for (const entry of entries) {
    if (entry === '.DS_Store' || entry.startsWith('bun.lock')) continue
    const full = join(dir, entry)
    let stats
    try {
      stats = lstatSync(full)
    } catch {
      continue
    }
    if (stats.isSymbolicLink()) continue
    if (stats.isDirectory()) {
      if (!SKIP_DIRS.has(entry)) yield* walkCodeFiles(full)
      continue
    }
    // Production and test sources are both scanned: a Better Auth import in a
    // test still requires the runtime package to be installed.
    if (CODE_EXTENSION.test(entry)) yield full
  }
}

const violations: Violation[] = []
for (const file of walkCodeFiles(WEB_ROOT)) {
  violations.push(...scanFile(file))
}

if (violations.length > 0) {
  console.error('')
  console.error('❌ Auth boundary check failed!')
  console.error('')
  console.error('LingxiLearn must not depend on Better Auth in production code. All')
  console.error('authentication is owned by the LingxiIdentity BFF (issue #52).')
  console.error('')
  console.error('Forbidden imports found:')
  for (const v of violations) {
    console.error(`  ${v.file}:${v.line}  →  '${v.specifier}'  (${v.boundary})`)
  }
  console.error('')
  console.error('If identity functionality is needed, extend the LingxiIdentity BFF')
  console.error('contract (lib/auth/identity-api.ts) instead of reinstalling Better Auth.')
  process.exit(1)
}

console.log('✅ Auth boundary check passed — no Better Auth imports in the web closure')
