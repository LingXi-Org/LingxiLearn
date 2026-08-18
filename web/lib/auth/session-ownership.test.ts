/**
 * @vitest-environment node
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * The SessionProvider is the single canonical owner of the browser session:
 * `identityApi.me()` (GET /api/v1/me) may only be called from
 * `lib/auth/session-provider.tsx`, and no module may reach for the removed
 * `client.getSession()` escape hatch. This scan is the regression guard for
 * that contract — a resource page or query module that starts fetching the
 * session on its own fails here, not in production as a request storm.
 */

const WEB_ROOT = process.cwd()

const FORBIDDEN_PATTERNS: Array<{ pattern: RegExp; label: string }> = [
  { pattern: /client\.getSession\s*\(/, label: 'client.getSession()' },
  { pattern: /identityApi\.me\s*\(/, label: 'identityApi.me()' },
]

const SCAN_DIRS = [
  'hooks/queries',
  'app/workspace/[workspaceId]/files',
  'app/workspace/[workspaceId]/knowledge',
  'app/workspace/[workspaceId]/tables',
]

function collectSourceFiles(dir: string): string[] {
  const collected: string[] = []
  for (const entry of readdirSync(dir)) {
    if (entry === 'node_modules' || entry === '.next') continue
    const full = join(dir, entry)
    const stats = statSync(full)
    if (stats.isDirectory()) {
      collected.push(...collectSourceFiles(full))
    } else if (/\.(ts|tsx)$/.test(entry)) {
      collected.push(full)
    }
  }
  return collected
}

describe('session request ownership', () => {
  it('resource pages and query modules never fetch the session themselves', () => {
    const violations: string[] = []

    for (const relativeDir of SCAN_DIRS) {
      for (const file of collectSourceFiles(join(WEB_ROOT, relativeDir))) {
        const source = readFileSync(file, 'utf8')
        for (const { pattern, label } of FORBIDDEN_PATTERNS) {
          const match = pattern.exec(source)
          if (match) {
            violations.push(`${file} calls ${label}`)
          }
        }
      }
    }

    expect(violations).toEqual([])
  })
})
