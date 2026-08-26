import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { extname, join, relative, resolve } from 'node:path'

const SOURCE_ROOTS = ['app', 'components', 'hooks', 'lib', 'stores', 'blocks', 'tools'] as const
const ROOT_FILES = [
  'proxy.ts',
  'instrumentation-client.ts',
  'instrumentation-node.ts',
  'instrumentation-edge.ts',
  'next.config.ts',
  'tsconfig.json',
  'tsconfig.frontend.json',
] as const
const SOURCE_EXTENSIONS = new Set(['.ts', '.tsx', '.js', '.jsx', '.json'])
const IGNORED_DIRECTORIES = new Set([
  'node_modules',
  '.next',
  'dist',
  'build',
  'coverage',
  '.turbo',
])
const WORKSPACE_COPY_FEATURES = new Set([
  'files',
  'home',
  'knowledge',
  'logs',
  'settings',
  'skills',
  'tables',
])

export const REMOVED_COMPATIBILITY_ROUTES = [
  'app/ingest/[[...path]]/route.ts',
  'app/desktop/auth/page.tsx',
  'app/desktop/connect/page.tsx',
  'app/desktop/done/page.tsx',
  'app/cli/auth/page.tsx',
  'app/oauth/chat-complete/page.tsx',
  'app/workspace/[workspaceId]/integrations/page.tsx',
  'app/workspace/[workspaceId]/integrations/[block]/page.tsx',
  'app/workspace/[workspaceId]/integrations/connected/[credentialId]/page.tsx',
] as const

export const REMOVED_COMPATIBILITY_FILES = [
  // Issue #40 completed only when callers use domain clients directly; a
  // facade recreates the cross-domain God object and a second API owner.
  'lib/lingxi/api.ts',
  // Schedules are explicitly not integrated in the Lingxi capability
  // manifest, so a query hook would expose an API with no backend owner.
  'hooks/queries/schedules.ts',
  // Billing and profile are owned outside the LingxiLearn API. These query
  // surfaces previously kept no-op billing and duplicate identity routes alive.
  'hooks/queries/subscription.ts',
  'hooks/queries/user-profile.ts',
  // Speech, provider allowlists, permission groups, and the legacy settings
  // shell all called API surfaces that LingxiLearn does not own.
  'hooks/use-speech-to-text.ts',
  'hooks/queries/voice.ts',
  'hooks/queries/allowed-providers.ts',
  'lib/api/contracts/media/speech.ts',
  'lib/api/contracts/permission-groups.ts',
  'lib/billing/workspace-permissions.ts',
  'components/settings/navigation.ts',
  'components/settings/standalone-settings-shell.tsx',
] as const

export const REMOVED_COMPATIBILITY_SOURCE_TREES = [
  // Issue #43 moved the reusable primitives out of the private workflow
  // editor. The Lingxi product has no workflow route or caller for this tree.
  'app/workspace/[workspaceId]/w',
  'app/workspace/[workspaceId]/integrations',
  'app/workspace/[workspaceId]/home/components/credits-chip',
  'app/workspace/[workspaceId]/components/connect-oauth-modal',
  'app/workspace/[workspaceId]/knowledge/[id]/components/add-connector-modal',
  'app/workspace/[workspaceId]/knowledge/[id]/components/connector-config-fields',
  'app/workspace/[workspaceId]/knowledge/[id]/components/connector-selector-field',
  'app/workspace/[workspaceId]/knowledge/[id]/components/connectors-section',
  'app/workspace/[workspaceId]/knowledge/[id]/components/edit-connector-modal',
  'app/workspace/[workspaceId]/settings/components/billing',
  'app/workspace/[workspaceId]/settings/components/browser',
  'app/workspace/[workspaceId]/settings/components/mcp',
  'app/workspace/[workspaceId]/settings/components/terminal',
] as const

export const WORKSPACE_COPY_OWNERS = [
  'app/workspace/[workspaceId]/components/lingxi-resource-page.tsx',
  'app/workspace/[workspaceId]/components/folders/foldered-resources.ts',
  'app/workspace/[workspaceId]/components/resource/resource.tsx',
  'app/workspace/[workspaceId]/files/files-list.tsx',
  'app/workspace/[workspaceId]/files/loading.tsx',
  'app/workspace/[workspaceId]/knowledge/knowledge.tsx',
  'app/workspace/[workspaceId]/knowledge/loading.tsx',
  'app/workspace/[workspaceId]/tables/tables.tsx',
  'app/workspace/[workspaceId]/tables/loading.tsx',
] as const

export interface QualityBoundaryViolation {
  file: string
  rule: string
}

function sourceFiles(directory: string): string[] {
  if (!existsSync(directory)) return []
  const files: string[] = []
  for (const entry of readdirSync(directory)) {
    if (IGNORED_DIRECTORIES.has(entry)) continue
    const path = join(directory, entry)
    if (statSync(path).isDirectory()) files.push(...sourceFiles(path))
    else if (SOURCE_EXTENSIONS.has(extname(path))) files.push(path)
  }
  return files
}

export function findQualityBoundaryViolations(webRoot: string): QualityBoundaryViolation[] {
  const files = [
    ...SOURCE_ROOTS.flatMap((directory) => sourceFiles(join(webRoot, directory))),
    ...ROOT_FILES.map((file) => join(webRoot, file)).filter(existsSync),
  ]
  const violations: QualityBoundaryViolation[] = []

  for (const file of files) {
    const content = readFileSync(file, 'utf8')
    const display = relative(webRoot, file).replaceAll('\\', '/')
    if (/['"]@sim(?:\/|['"])/.test(content)) {
      violations.push({ file: display, rule: 'deleted @sim/* package alias' })
    }
    if (!display.startsWith('stores/') && /['"]@\/stores\/[^'"]+\/types['"]/.test(content)) {
      violations.push({ file: display, rule: 'domain types must not be owned by a store' })
    }
    if (/^\s*\/\/\s*@ts-nocheck\b/m.test(content)) {
      violations.push({ file: display, rule: '@ts-nocheck disables production checking' })
    }
    if (/\bnoCheck\s*[":=]/.test(content)) {
      violations.push({ file: display, rule: 'TypeScript noCheck bypass' })
    }
    if (/\bignoreBuildErrors\s*[":=]/.test(content)) {
      violations.push({ file: display, rule: 'Next.js ignoreBuildErrors bypass' })
    }
    const workspaceMatch = display.match(/^app\/workspace\/\[workspaceId\]\/([^/]+)\//)
    if (
      workspaceMatch &&
      WORKSPACE_COPY_FEATURES.has(workspaceMatch[1]) &&
      /(?:set(?:Error|[A-Z]\w*Error)\([^\n]*(?:getErrorMessage|toError\([^)]*\)\.message|(?:error|err|cause)\??\.message)|toast\.error\([^\n]*(?:getErrorMessage|toError\([^)]*\)\.message|(?:error|err|cause)\??\.message)|description:\s*(?:getErrorMessage|toError\([^)]*\)\.message|(?:error|err|cause)\??\.message)|\{getErrorMessage\([^}]+\)\}|mutation\.error\?*\.message)/.test(
        content
      )
    ) {
      violations.push({ file: display, rule: 'raw technical error exposed in Workspace UI' })
    }
  }

  for (const route of REMOVED_COMPATIBILITY_ROUTES) {
    if (existsSync(join(webRoot, ...route.split('/')))) {
      violations.push({ file: route, rule: 'removed fake compatibility route was restored' })
    }
  }
  for (const file of REMOVED_COMPATIBILITY_FILES) {
    if (existsSync(join(webRoot, ...file.split('/')))) {
      violations.push({ file, rule: 'removed compatibility source was restored' })
    }
  }
  for (const directory of REMOVED_COMPATIBILITY_SOURCE_TREES) {
    const path = join(webRoot, ...directory.split('/'))
    if (sourceFiles(path).length > 0) {
      violations.push({ file: directory, rule: 'removed compatibility source tree was restored' })
    }
  }
  for (const owner of WORKSPACE_COPY_OWNERS) {
    const path = join(webRoot, ...owner.split('/'))
    if (existsSync(path) && !readFileSync(path, 'utf8').includes('@/lib/product-copy')) {
      violations.push({ file: owner, rule: 'shared Workspace copy must use the product catalog' })
    }
  }
  const specialTags = join(
    webRoot,
    'app',
    'workspace',
    '[workspaceId]',
    'home',
    'components',
    'message-content',
    'components',
    'special-tags',
    'special-tags.tsx'
  )
  if (existsSync(specialTags)) {
    const source = readFileSync(specialTags, 'utf8')
    for (const tagType of [
      'link',
      'oauth_key',
      'secret_input',
      'sim_key',
      'service_account',
      'folder_access',
    ]) {
      if (source.includes(`'${tagType}'`) || source.includes(`"${tagType}"`)) {
        violations.push({
          file: relative(webRoot, specialTags).replaceAll('\\', '/'),
          rule: `unsupported credential tag '${tagType}' was restored`,
        })
      }
    }
  }
  const chatQueries = join(webRoot, 'hooks', 'queries', 'mothership-chats.ts')
  if (existsSync(chatQueries)) {
    const source = readFileSync(chatQueries, 'utf8')
    if (
      source.includes('unsupportedMutation') ||
      source.includes('该共享功能未接入 LingxiGraph') ||
      /mutationFn:\s*async\s*\([^)]*\)\s*=>\s*undefined/.test(source)
    ) {
      violations.push({
        file: 'hooks/queries/mothership-chats.ts',
        rule: 'native task mutations must not use fake success or unsupported shims',
      })
    }
  }
  return violations
}

if (import.meta.main) {
  const webRoot = resolve(import.meta.dirname, '..')
  const violations = findQualityBoundaryViolations(webRoot)
  if (violations.length > 0) {
    console.error('Production quality boundary violations:')
    for (const violation of violations) console.error(`- ${violation.file}: ${violation.rule}`)
    process.exit(1)
  }
  console.log('Production quality boundaries passed.')
}
