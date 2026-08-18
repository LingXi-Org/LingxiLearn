/**
 * @vitest-environment node
 */
import { describe, expect, it } from 'vitest'

import { resolveSettingsHref } from '@/hooks/use-settings-navigation'

describe('resolveSettingsHref unified settings navigation', () => {
  it('preserves MCP server query parameters for workspace settings', () => {
    expect(
      resolveSettingsHref({
        options: { section: 'mcp', mcpServerId: 'server/a' },
        workspaceId: 'workspace-b',
      })
    ).toBe('/workspace/workspace-b/settings/mcp?mcpServerId=server%2Fa')
  })

  it('routes the removed billing section back to general settings (issue #54)', () => {
    expect(
      resolveSettingsHref({
        options: { section: 'billing' },
        workspaceId: 'workspace-b',
      })
    ).toBe('/workspace/workspace-b/settings/general')
  })

  it('defaults to the general settings section', () => {
    expect(resolveSettingsHref({ workspaceId: 'workspace-b' })).toBe(
      '/workspace/workspace-b/settings/general'
    )
  })
})
