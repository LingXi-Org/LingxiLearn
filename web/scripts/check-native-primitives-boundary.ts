/** Prevent migrated Sim primitives from returning to application code. */
import { spawnSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
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
  [`${legacyScope}/db`, 'deleted (no current caller)'],
  [`${legacyScope}/db/constants`, 'deleted (no current caller)'],
  [`${legacyScope}/db/schema`, 'deleted (no current caller)'],
  [`${legacyScope}/db/triggers`, 'deleted (no current caller)'],
  [`${legacyScope}/db/types`, 'deleted (no current caller)'],
  [`${legacyScope}/desktop-bridge`, '@/lib/desktop/bridge'],
  [`${legacyScope}/desktop-bridge/local-filesystem-limits`, 'deleted (no current caller)'],
  [`${legacyScope}/emcn`, '@/components/ui-kit'],
  [`${legacyScope}/emcn/code.css`, '@/components/ui-kit/components/code/code.css'],
  [`${legacyScope}/emcn/icons`, '@/components/ui-kit/icons'],
  [`${legacyScope}/runtime-secrets`, 'deleted (no current caller)'],
  [`${legacyScope}/platform-authz/predicates`, 'deleted (no current caller)'],
  [`${legacyScope}/platform-authz/room-policy`, 'deleted (no current caller)'],
  [`${legacyScope}/platform-authz/rooms`, 'deleted (no current caller)'],
  [`${legacyScope}/platform-authz/workflow`, 'deleted (no current caller)'],
  [`${legacyScope}/platform-authz/workspace`, 'deleted (no current caller)'],
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
  [`${legacyScope}/security/hmac`, 'deleted (no current caller)'],
  [`${legacyScope}/security/hostnames`, '@/lib/security/hostnames'],
  [`${legacyScope}/security/ssrf`, '@/lib/security/ssrf'],
  [`${legacyScope}/security/tokens`, 'deleted (no current caller)'],
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
  [`${legacyScope}/workflow-persistence`, 'deleted (no current caller)'],
  [`${legacyScope}/workflow-persistence/load`, 'deleted (no current caller)'],
  [`${legacyScope}/workflow-persistence/save`, 'deleted (no current caller)'],
  [`${legacyScope}/workflow-persistence/subblocks`, '@/lib/workflows/persistence/native/subblocks'],
  [`${legacyScope}/workflow-persistence/subflow-helpers`, 'deleted (no current caller)'],
  [`${legacyScope}/workflow-persistence/types`, 'deleted (no current caller)'],
  [`${legacyScope}/logger`, '@/lib/logger'],
  [`${legacyScope}/utils/errors`, '@/lib/utils/errors'],
  [`${legacyScope}/utils/id`, '@/lib/utils/id'],
  [`${legacyScope}/utils/object`, '@/lib/utils/object'],
  [`${legacyScope}/utils/string`, '@/lib/utils/string'],
  [`${legacyScope}/utils/fractional-indexing`, 'deleted (no current caller)'],
  [`${legacyScope}/utils`, '@/lib/utils'],
  [`${legacyScope}/utils/color`, '@/lib/utils/color'],
  [`${legacyScope}/utils/formatting`, '@/lib/utils/formatting'],
  [`${legacyScope}/utils/helpers`, '@/lib/utils/helpers'],
  [`${legacyScope}/utils/media-embed`, '@/lib/utils/media-embed'],
  [`${legacyScope}/utils/random`, '@/lib/utils/random'],
  [`${legacyScope}/utils/retry`, '@/lib/utils/retry'],
  [`${legacyScope}/utils/sandbox-references`, '@/lib/utils/sandbox-references'],
  [`${legacyScope}/utils/sso-domain`, 'deleted (no current caller)'],
])
const moduleSpecifier = /(?:from\s*|import\s*|require\s*\(|import\s*\(\s*)['"]([^'"]+)['"]/
const violations: string[] = []

function scanSourceImports(): void {
  const result = spawnSync('git', ['-C', root, 'ls-files', '-z'], { encoding: 'utf8' })
  if (result.status !== 0) {
    throw new Error(result.stderr || `git ls-files failed with status ${result.status}`)
  }

  const sourceExtension = /\.(?:[cm]?[jt]sx?)$/
  for (const trackedPath of result.stdout.split('\0').filter(Boolean)) {
    const relativePath = trackedPath.replace(/^web\//, '')
    const segments = relativePath.split('/')
    if (!sourceExtension.test(relativePath) || segments.some((part) => skipped.has(part))) continue
    if (
      [...skippedRelativeDirectories].some((directory) => relativePath.startsWith(`${directory}/`))
    ) {
      continue
    }

    const file = resolve(root, relativePath)
    // Alternate worktree metadata can briefly list a path removed by the active index.
    if (!existsSync(file)) continue
    const lines = readFileSync(file, 'utf8').split(/\r?\n/)
    for (const [index, line] of lines.entries()) {
      if (!line.includes(`${legacyScope}/`)) continue
      const specifier = moduleSpecifier.exec(line)?.[1]
      if (specifier && migrated.has(specifier)) {
        violations.push(
          `${relative(root, file)}:${index + 1}: ${specifier} → ${migrated.get(specifier)}`
        )
      }
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
