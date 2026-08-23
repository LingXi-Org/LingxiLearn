/**
 * @vitest-environment node
 */
import { describe, expect, it } from 'vitest'
import { Integration } from '@/components/ui-kit/icons'
import { getConnectorMeta } from '@/connectors/registry'
import { resolveConnectorBadges } from '@/app/workspace/[workspaceId]/knowledge/presentation/connector-cell'

describe('resolveConnectorBadges', () => {
  it('returns no badges for a base without connectors', () => {
    expect(resolveConnectorBadges(undefined)).toEqual([])
    expect(resolveConnectorBadges([])).toEqual([])
  })

  it('resolves registered connector types to their metadata', () => {
    const meta = getConnectorMeta('notion')
    expect(meta).toBeDefined()

    const [badge] = resolveConnectorBadges(['notion'])
    expect(badge.type).toBe('notion')
    expect(badge.name).toBe(meta?.name)
    expect(badge.Icon).toBe(meta?.icon)
  })

  it('keeps an unknown connector type with a generic icon and the raw type as label', () => {
    // A type missing from the registry — a retired connector, or one created by a newer
    // server — must never drop the row's badge: it falls back to a stable label and a
    // generic icon instead.
    const [badge] = resolveConnectorBadges(['connector-from-the-future'])
    expect(badge.type).toBe('connector-from-the-future')
    expect(badge.name).toBe('connector-from-the-future')
    expect(badge.Icon).toBe(Integration)
  })

  it('mixes known and unknown types without dropping either', () => {
    const badges = resolveConnectorBadges(['notion', 'mystery-connector'])
    expect(badges.map((badge) => badge.type)).toEqual(['notion', 'mystery-connector'])
    expect(badges[1].Icon).toBe(Integration)
    expect(badges[1].name).toBe('mystery-connector')
  })
})
