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
  'app/workspace/[workspaceId]/integrations/page.tsx',
  'app/workspace/[workspaceId]/integrations/[block]/page.tsx',
  'app/workspace/[workspaceId]/integrations/connected/[credentialId]/page.tsx',
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
  for (const owner of WORKSPACE_COPY_OWNERS) {
    const path = join(webRoot, ...owner.split('/'))
    if (existsSync(path) && !readFileSync(path, 'utf8').includes('@/lib/product-copy')) {
      violations.push({ file: owner, rule: 'shared Workspace copy must use the product catalog' })
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
