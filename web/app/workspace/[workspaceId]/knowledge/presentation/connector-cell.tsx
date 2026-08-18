import type { ComponentType } from 'react'
import { Tooltip } from '@sim/emcn'
import { Integration } from '@sim/emcn/icons'
import type { ResourceCell } from '@/app/workspace/[workspaceId]/components'
import { EMPTY_CELL_PLACEHOLDER } from '@/app/workspace/[workspaceId]/components'
import { getConnectorMeta } from '@/connectors/registry'

/**
 * The maximum number of connector badges rendered inline before collapsing into a
 * `+N` overflow badge.
 */
const MAX_VISIBLE_BADGES = 3

/**
 * Presentation-only view of one connector type: everything the list cell renders, resolved
 * from the connector registry. The knowledge domain deals in connector type STRINGS (the
 * `connectorTypes` on a knowledge base); this adapter is the only place that turns those
 * strings into an icon and a label, so the registry stays a presentation dependency rather
 * than an implicit business owner of the knowledge list.
 */
export interface ConnectorBadge {
  type: string
  name: string
  Icon: ComponentType<{ className?: string }>
}

/**
 * Resolves connector type strings to badges. A type missing from the registry — a retired
 * connector, or one created by a newer server than this bundle — falls back to a generic
 * icon labeled with the raw type, so the cell stays stable instead of silently dropping it.
 */
export function resolveConnectorBadges(connectorTypes?: string[]): ConnectorBadge[] {
  if (!connectorTypes || connectorTypes.length === 0) return []

  return connectorTypes.map((type) => {
    const meta = getConnectorMeta(type)
    return meta
      ? { type, name: meta.name, Icon: meta.icon }
      : { type, name: type, Icon: Integration }
  })
}

/**
 * Builds the "Connectors" cell for a knowledge base row: up to three icon badges plus a
 * `+N` overflow, each with a tooltip. Empty when the base has no connectors.
 */
export function connectorCell(connectorTypes?: string[]): ResourceCell {
  const badges = resolveConnectorBadges(connectorTypes)
  if (badges.length === 0) return { label: EMPTY_CELL_PLACEHOLDER }

  const visibleBadges = badges.slice(0, MAX_VISIBLE_BADGES)
  const hiddenBadges = badges.slice(MAX_VISIBLE_BADGES)

  return {
    content: (
      <div className='flex items-center gap-1'>
        {visibleBadges.map(({ type, name, Icon }) => (
          <Tooltip.Root key={type}>
            <Tooltip.Trigger asChild>
              <span className='flex size-5 flex-shrink-0 items-center justify-center rounded-md bg-[var(--surface-4)] text-[var(--text-secondary)]'>
                <Icon className='size-[13px]' />
              </span>
            </Tooltip.Trigger>
            <Tooltip.Content>{name}</Tooltip.Content>
          </Tooltip.Root>
        ))}
        {hiddenBadges.length > 0 && (
          <Tooltip.Root>
            <Tooltip.Trigger asChild>
              <span className='flex size-5 flex-shrink-0 items-center justify-center rounded-md bg-[var(--surface-4)] font-medium text-[var(--text-muted)] text-micro'>
                +{hiddenBadges.length}
              </span>
            </Tooltip.Trigger>
            <Tooltip.Content>{hiddenBadges.map(({ name }) => name).join(', ')}</Tooltip.Content>
          </Tooltip.Root>
        )}
      </div>
    ),
  }
}
