/** Prevent the deleted legacy logger package from returning to application code. */
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
const codeExtension = /\.(?:ts|tsx|js|jsx|mjs|cjs)$/
const legacyLogger = `@${'sim'}/logger`
const forbidden = new RegExp(
  String.raw`(?:from\s*|import\s*|require\s*\(|import\s*\(\s*)['"]${legacyLogger}(?:\/[^'"]*)?['"]`
)
const violations: string[] = []

function scan(directory: string): void {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (!skipped.has(entry.name)) scan(join(directory, entry.name))
      continue
    }
    if (!codeExtension.test(entry.name)) continue
    const file = join(directory, entry.name)
    const lines = readFileSync(file, 'utf8').split('\n')
    for (let index = 0; index < lines.length; index += 1) {
      if (forbidden.test(lines[index])) {
        violations.push(`${relative(root, file)}:${index + 1}: ${lines[index].trim()}`)
      }
    }
  }
}

scan(root)
if (violations.length > 0) {
  console.error(`Deleted ${legacyLogger} boundary was reintroduced:\n`)
  console.error(violations.join('\n'))
  process.exit(1)
}
console.log('Native logger boundary check passed.')
