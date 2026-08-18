/**
 * @vitest-environment node
 */
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

import {
  isLingxiCapabilityIntegrated,
  LingxiCapabilityManifest,
  LINGXI_WORKSPACE_ROUTE_ALLOWLIST,
} from '@/lib/lingxi/capabilities'

/** The `web/` root, anchored to this file rather than `process.cwd()`. */
const WEB_ROOT = path.resolve(__dirname, '..', '..')
const webPath = (...segments: string[]) => path.join(WEB_ROOT, ...segments)

/**
 * Compatibility routes removed in issue #48. They existed only to preserve
 * Sim route shapes (constant 404s, redirects, placeholder UI) while LingxiLearn
 * has no product caller for them. Unsupported capabilities must be expressed by
 * the code not existing — if one of these trees is copied back in from upstream
 * Sim, this gate fails and the reintroduction has to be deliberate.
 */
const REMOVED_COMPATIBILITY_ROUTES = [
  'app/ingest/[[...path]]/route.ts',
  'app/desktop/auth/page.tsx',
  'app/desktop/connect/page.tsx',
  'app/desktop/done/page.tsx',
  'app/cli/auth/page.tsx',
  'app/workspace/[workspaceId]/integrations/page.tsx',
  'app/workspace/[workspaceId]/integrations/[block]/page.tsx',
  'app/workspace/[workspaceId]/integrations/connected/[credentialId]/page.tsx',
] as const

describe('capability allowlist (issue #48)', () => {
  it('keeps removed compatibility routes deleted', () => {
    const revived = REMOVED_COMPATIBILITY_ROUTES.filter((route) => existsSync(webPath(route)))
    expect(revived).toEqual([])
  })

  it('marks the removed surfaces as not integrated', () => {
    for (const capability of ['integrations', 'desktop', 'cli', 'ingest'] as const) {
      expect(LingxiCapabilityManifest[capability].status).toBe('not_integrated')
      expect(isLingxiCapabilityIntegrated(capability)).toBe(false)
    }
  })

  it('derives the route allowlist only from integrated capabilities', () => {
    expect(LINGXI_WORKSPACE_ROUTE_ALLOWLIST.length).toBeGreaterThan(0)
    expect([...LINGXI_WORKSPACE_ROUTE_ALLOWLIST].sort()).toEqual(
      ['files', 'knowledge', 'logs', 'skills', 'tables'].sort()
    )
    for (const [key, capability] of Object.entries(LingxiCapabilityManifest)) {
      if ('routeSegment' in capability && capability.routeSegment) {
        expect(capability.status, key).toBe('integrated')
        expect(LINGXI_WORKSPACE_ROUTE_ALLOWLIST).toContain(capability.routeSegment)
      }
    }
  })

  it('navigates only to allowlisted workspace segments', () => {
    // The workspace sidebar is the product navigation surface; every segment
    // it links to must exist in the capability-derived route allowlist, so nav
    // visibility and route availability stay decided by the same fact.
    const sidebar = readFileSync(
      webPath('app', 'workspace', '[workspaceId]', 'components', 'workspace-chrome', 'sim-sidebar.tsx'),
      'utf8'
    )
    const segments = [...sidebar.matchAll(/segment:\s*'([^']+)'/g)].map((match) => match[1])
    expect(segments.length).toBeGreaterThan(0)
    for (const segment of segments) {
      expect(LINGXI_WORKSPACE_ROUTE_ALLOWLIST, `sidebar segment '${segment}'`).toContain(segment)
    }
  })
})
