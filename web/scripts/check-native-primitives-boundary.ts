/** Prevent migrated Sim primitives from returning to application code. */
import { readdirSync, readFileSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const skipped = new Set([
  'node_modules',
  '.next',
  '.turbo',
  '.git',
  'coverage',
  'dist',
  'build',
  'var',
  'public',
])
const skippedRelativeDirectories = new Set(['lib/execution/sandbox/bundles'])
const codeExtension = /\.(?:ts|tsx|js|jsx|mjs|cjs)$/
const legacyScope = `@${'sim'}`
const migrated = new Map([
  [`${legacyScope}/logger`, '@/lib/logger'],
  [`${legacyScope}/utils/errors`, '@/lib/utils/errors'],
  [`${legacyScope}/utils/id`, '@/lib/utils/id'],
  [`${legacyScope}/utils/object`, '@/lib/utils/object'],
  [`${legacyScope}/utils/string`, '@/lib/utils/string'],
  [`${legacyScope}/utils/fractional-indexing`, '@/lib/utils/fractional-indexing'],
])
const moduleSpecifier = /(?:from\s*|import\s*|require\s*\(|import\s*\(\s*)['"]([^'"]+)['"]/
const violations: string[] = []

function scan(directory: string): void {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      const child = join(directory, entry.name)
      const childRelative = relative(root, child).replaceAll('\\', '/')
      if (!skipped.has(entry.name) && !skippedRelativeDirectories.has(childRelative)) scan(child)
      continue
    }
    if (!codeExtension.test(entry.name)) continue
    const file = join(directory, entry.name)
    const lines = readFileSync(file, 'utf8').split('\n')
    for (let index = 0; index < lines.length; index += 1) {
      const specifier = moduleSpecifier.exec(lines[index])?.[1]
      if (specifier && migrated.has(specifier)) {
        violations.push(
          `${relative(root, file)}:${index + 1}: ${specifier} → ${migrated.get(specifier)}`
        )
      }
    }
  }
}

scan(root)
if (violations.length > 0) {
  console.error('A migrated Sim primitive boundary was reintroduced:\n')
  console.error(violations.join('\n'))
  process.exit(1)
}
console.log('Native primitive boundary check passed.')
