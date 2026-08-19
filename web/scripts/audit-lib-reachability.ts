import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'

const root = process.cwd()
const libRoot = path.join(root, 'lib')
const sourceExtensions = ['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs']
const importPattern =
  /(?:import|export)\s+(?:type\s+)?(?:[^'";]*?\s+from\s+)?['"]([^'"]+)['"]|import\(\s*(?:\/\*[\s\S]*?\*\/\s*)?['"]([^'"]+)['"]\s*\)|require(?:\.resolve)?\(\s*['"]([^'"]+)['"]\s*\)/g
const dynamicImportPattern = /\bimport\(([\s\S]*?)\)/g

function filesUnder(directory: string): string[] {
  if (!existsSync(directory)) return []
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    if (entry.isDirectory() && ['node_modules', '.next', 'coverage'].includes(entry.name)) return []
    const target = path.join(directory, entry.name)
    return entry.isDirectory() ? filesUnder(target) : [target]
  })
}

function isSource(file: string): boolean {
  return sourceExtensions.includes(path.extname(file))
}

function isTest(file: string): boolean {
  return /(?:^|[\\/])(?:__tests__|tests?)(?:[\\/]|$)|\.(?:test|spec)\.[^.]+$/.test(file)
}

function resolveSource(base: string): string | undefined {
  const candidates = [
    base,
    ...sourceExtensions.map((extension) => `${base}${extension}`),
    ...sourceExtensions.map((extension) => path.join(base, `index${extension}`)),
  ]
  return candidates.find((candidate) => existsSync(candidate) && statSync(candidate).isFile())
}

function resolveImport(from: string, specifier: string): string | undefined {
  if (specifier.startsWith('@/')) return resolveSource(path.join(root, specifier.slice(2)))
  if (specifier.startsWith('.')) return resolveSource(path.resolve(path.dirname(from), specifier))
  return undefined
}

function importsOf(file: string): string[] {
  const source = readFileSync(file, 'utf8')
  const imports: string[] = []
  for (const match of source.matchAll(importPattern)) {
    const resolved = resolveImport(file, match[1] ?? match[2] ?? match[3])
    if (resolved) imports.push(resolved)
  }
  return imports
}

function reachableFrom(entries: string[]): Set<string> {
  const reached = new Set<string>()
  const pending = [...entries]
  while (pending.length > 0) {
    const file = pending.pop()
    if (!file || reached.has(file)) continue
    reached.add(file)
    for (const imported of importsOf(file)) pending.push(imported)
  }
  return reached
}

const nextEntryPattern =
  /(?:^|[\\/])(?:page|layout|route|default|error|global-error|loading|not-found|unauthorized|forbidden|template|opengraph-image|twitter-image|sitemap|robots|manifest|icon)\.(?:ts|tsx|js|jsx)$/
const rootEntries = [
  'bootstrap.ts',
  'drizzle.config.ts',
  'instrumentation.ts',
  'instrumentation-client.ts',
  'instrumentation-edge.ts',
  'instrumentation-node.ts',
  'next.config.ts',
  'proxy.ts',
  'telemetry.config.ts',
  'trigger.config.ts',
  'lib/execution/isolated-vm-worker.cjs',
  'lib/execution/sandbox/bundles/pptxgenjs.cjs',
  'lib/execution/sandbox/bundles/docx.cjs',
  'lib/execution/sandbox/bundles/pdf-lib.cjs',
]
  .map((entry) => path.join(root, entry))
  .filter(existsSync)
const productionEntries = [
  ...filesUnder(path.join(root, 'app')).filter((file) => nextEntryPattern.test(file)),
  ...filesUnder(path.join(root, 'background')).filter(isSource),
  ...rootEntries,
].filter((file) => !isTest(file))
const testEntries = filesUnder(root).filter(
  (file) => isSource(file) && isTest(file) && !file.includes(`${path.sep}node_modules${path.sep}`)
)
const production = reachableFrom(productionEntries)
const tests = reachableFrom(testEntries)
const unresolvedDynamicImports = [...production].flatMap((file) => {
  const source = readFileSync(file, 'utf8')
  return [...source.matchAll(dynamicImportPattern)].flatMap((match) => {
    const argument = match[1].trim().replace(/^(?:\/\*[\s\S]*?\*\/\s*)+/, '')
    if (argument.length === 0) return []
    if (argument.startsWith("'") || argument.startsWith('"')) return []
    return [
      {
        file: path.relative(root, file).replaceAll('\\', '/'),
        expression: match[0],
      },
    ]
  })
})

const inventory = readdirSync(libRoot, { withFileTypes: true })
  .filter((entry) => entry.isDirectory())
  .map((entry) => {
    const files = filesUnder(path.join(libRoot, entry.name)).filter(isSource)
    const productionFiles = files.filter((file) => production.has(file)).length
    const testFiles = files.filter((file) => tests.has(file)).length
    const unreachableFiles = files.filter((file) => !production.has(file) && !tests.has(file))
    return {
      directory: entry.name,
      sourceFiles: files.length,
      productionFiles,
      testFiles,
      unreachableFiles: unreachableFiles.length,
      sampleProductionFiles: files
        .filter((file) => production.has(file))
        .slice(0, 5)
        .map((file) => path.relative(root, file).replaceAll('\\', '/')),
      sampleUnreachableFiles: unreachableFiles
        .slice(0, 5)
        .map((file) => path.relative(root, file).replaceAll('\\', '/')),
      classification:
        productionFiles > 0 ? 'production-reachable' : testFiles > 0 ? 'test-only' : 'unreachable',
    }
  })
  .filter((entry) => entry.sourceFiles > 0)
  .sort((left, right) => left.directory.localeCompare(right.directory))

process.stdout.write(
  `${JSON.stringify(
    {
      productionEntrypoints: productionEntries.map((file) =>
        path.relative(root, file).replaceAll('\\', '/')
      ),
      unresolvedDynamicImports,
      inventory,
    },
    null,
    2
  )}\n`
)
