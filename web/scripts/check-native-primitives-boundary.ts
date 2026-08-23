/** Prevent migrated Sim primitives from returning to application code. */
import { spawnSync } from 'node:child_process'
import { relative, resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const skipped = new Set([
  'node_modules',
  '.next',
  '.turbo',
  '.venv',
  '.pytest_cache',
  '.git',
  'coverage',
  'dist',
  'build',
  'var',
  'public',
])
const skippedRelativeDirectories = new Set(['lib/execution/sandbox/bundles'])
const legacyScope = `@${'sim'}`
const migrated = new Map([
  [`${legacyScope}/audit`, '@/lib/audit'],
  [`${legacyScope}/browser-protocol`, '@/lib/browser-agent/protocol'],
  [`${legacyScope}/db`, '@/lib/db'],
  [`${legacyScope}/db/constants`, '@/lib/db/constants'],
  [`${legacyScope}/db/schema`, '@/lib/db/schema'],
  [`${legacyScope}/db/triggers`, '@/lib/db/triggers'],
  [`${legacyScope}/db/types`, '@/lib/db/types'],
  [`${legacyScope}/desktop-bridge`, '@/lib/desktop/bridge'],
  [
    `${legacyScope}/desktop-bridge/local-filesystem-limits`,
    '@/lib/desktop/local-filesystem-limits',
  ],
  [`${legacyScope}/emcn`, '@/components/ui-kit'],
  [`${legacyScope}/emcn/code.css`, '@/components/ui-kit/code.css'],
  [`${legacyScope}/emcn/icons`, '@/components/ui-kit/icons'],
  [`${legacyScope}/runtime-secrets`, '@/lib/environment/runtime-secrets'],
  [`${legacyScope}/platform-authz/predicates`, '@/lib/permissions/native/predicates'],
  [`${legacyScope}/platform-authz/room-policy`, 'deleted (no current caller)'],
  [`${legacyScope}/platform-authz/rooms`, 'deleted (no current caller)'],
  [`${legacyScope}/platform-authz/workflow`, '@/lib/permissions/native/workflow'],
  [`${legacyScope}/platform-authz/workspace`, '@/lib/permissions/native/workspace'],
  [`${legacyScope}/realtime-protocol/constants`, '@/lib/realtime/protocol/constants'],
  [`${legacyScope}/realtime-protocol/events`, '@/lib/realtime/protocol/events'],
  [`${legacyScope}/realtime-protocol/file-doc`, '@/lib/realtime/protocol/file-doc'],
  [`${legacyScope}/realtime-protocol/rooms`, '@/lib/realtime/protocol/rooms'],
  [`${legacyScope}/realtime-protocol/schemas`, 'deleted (no current caller)'],
  [`${legacyScope}/realtime-protocol/table-presence`, 'deleted (no current caller)'],
  [`${legacyScope}/security/compare`, '@/lib/security/compare'],
  [`${legacyScope}/security/dns`, '@/lib/security/dns'],
  [`${legacyScope}/security/encryption`, '@/lib/security/encryption'],
  [`${legacyScope}/security/hash`, '@/lib/security/hash'],
  [`${legacyScope}/security/hmac`, '@/lib/security/hmac'],
  [`${legacyScope}/security/hostnames`, '@/lib/security/hostnames'],
  [`${legacyScope}/security/ssrf`, '@/lib/security/ssrf'],
  [`${legacyScope}/security/tokens`, '@/lib/security/tokens'],
  [`${legacyScope}/terminal-protocol`, '@/lib/terminal/protocol'],
  [`${legacyScope}/testing`, '@/tests/support'],
  [`${legacyScope}/testing/assertions`, '@/tests/support/assertions'],
  [`${legacyScope}/testing/builders`, '@/tests/support/builders'],
  [`${legacyScope}/testing/environment`, '@/tests/support/environment'],
  [`${legacyScope}/testing/factories`, '@/tests/support/factories'],
  [`${legacyScope}/testing/mocks`, '@/tests/support/mocks'],
  [`${legacyScope}/testing/setup`, '@/tests/support/setup'],
  [`${legacyScope}/testing/types`, '@/tests/support/types'],
  [`${legacyScope}/workflow-types/blocks`, '@/lib/workflows/domain/blocks'],
  [`${legacyScope}/workflow-types/workflow`, '@/lib/workflows/domain/workflow'],
  [`${legacyScope}/workflow-renderer`, '@/components/workflow'],
  [`${legacyScope}/workflow-renderer/note-colors`, '@/components/workflow/note/note-colors'],
  [`${legacyScope}/workflow-persistence`, '@/lib/workflows/persistence/native'],
  [`${legacyScope}/workflow-persistence/load`, '@/lib/workflows/persistence/native/load'],
  [`${legacyScope}/workflow-persistence/save`, '@/lib/workflows/persistence/native/save'],
  [`${legacyScope}/workflow-persistence/subblocks`, '@/lib/workflows/persistence/native/subblocks'],
  [
    `${legacyScope}/workflow-persistence/subflow-helpers`,
    '@/lib/workflows/persistence/native/subflow-helpers',
  ],
  [`${legacyScope}/workflow-persistence/types`, '@/lib/workflows/persistence/native/types'],
  [`${legacyScope}/logger`, '@/lib/logger'],
  [`${legacyScope}/utils/errors`, '@/lib/utils/errors'],
  [`${legacyScope}/utils/id`, '@/lib/utils/id'],
  [`${legacyScope}/utils/object`, '@/lib/utils/object'],
  [`${legacyScope}/utils/string`, '@/lib/utils/string'],
  [`${legacyScope}/utils/fractional-indexing`, '@/lib/utils/fractional-indexing'],
  [`${legacyScope}/utils`, '@/lib/utils'],
  [`${legacyScope}/utils/color`, '@/lib/utils/color'],
  [`${legacyScope}/utils/formatting`, '@/lib/utils/formatting'],
  [`${legacyScope}/utils/helpers`, '@/lib/utils/helpers'],
  [`${legacyScope}/utils/media-embed`, '@/lib/utils/media-embed'],
  [`${legacyScope}/utils/random`, '@/lib/utils/random'],
  [`${legacyScope}/utils/retry`, '@/lib/utils/retry'],
  [`${legacyScope}/utils/sandbox-references`, '@/lib/utils/sandbox-references'],
  [`${legacyScope}/utils/sso-domain`, '@/lib/utils/sso-domain'],
])
const moduleSpecifier = /(?:from\s*|import\s*|require\s*\(|import\s*\(\s*)['"]([^'"]+)['"]/
const violations: string[] = []

function scanSourceImports(): void {
  const args = ['-n', '--no-heading']
  for (const extension of ['ts', 'tsx', 'js', 'jsx', 'mjs', 'cjs']) args.push('--glob', `*.${extension}`)
  for (const directory of skipped) args.push('--glob', `!${directory}/**`)
  for (const directory of skippedRelativeDirectories) args.push('--glob', `!${directory}/**`)
  args.push(`${legacyScope}/`, root)
  const result = spawnSync('rg', args, { encoding: 'utf8' })
  if (result.status !== 0 && result.status !== 1) {
    throw new Error(result.stderr || `ripgrep failed with status ${result.status}`)
  }
  for (const match of result.stdout.split(/\r?\n/).filter(Boolean)) {
    const firstColon = match.indexOf(':')
    const secondColon = match.indexOf(':', firstColon + 1)
    if (firstColon < 0 || secondColon < 0) continue
    const file = match.slice(0, firstColon)
    const lineNumber = match.slice(firstColon + 1, secondColon)
    const line = match.slice(secondColon + 1)
    const specifier = moduleSpecifier.exec(line)?.[1]
    if (specifier && migrated.has(specifier)) {
      violations.push(
        `${relative(root, file)}:${lineNumber}: ${specifier} → ${migrated.get(specifier)}`
      )
    }
  }
}

scanSourceImports()
if (violations.length > 0) {
  console.error('A migrated Sim primitive boundary was reintroduced:\n')
  console.error(violations.join('\n'))
  process.exit(1)
}
console.log('Native primitive boundary check passed.')
