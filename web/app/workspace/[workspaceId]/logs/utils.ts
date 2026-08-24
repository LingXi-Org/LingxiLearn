import React from 'react'
import { format } from 'date-fns'
import { Badge } from '@/components/ui-kit'
import { formatDuration, formatRelativeTime } from '@/lib/utils/formatting'
import type { RunStatus, TriggerPresentation } from './model/execution-log'

/** Wire-compatibility fallback for historical dashboard rows with deleted sources. */
export const DELETED_WORKFLOW_LABEL = 'Deleted source'

/**
 * Presentation helpers for the logs surface. Domain facts (status, duration,
 * source, trigger) are resolved upstream by the pure observability mapper
 * (`model/execution-log-mapper`); these components only render them.
 */

export const STATUS_CONFIG: Record<
  RunStatus,
  {
    variant: React.ComponentProps<typeof Badge>['variant']
    label: string
    color: string
    /** Whether this status appears as a filter option. Intermediary states (e.g. cancelling) are excluded. */
    filterable: boolean
  }
> = {
  error: { variant: 'red', label: 'Error', color: 'var(--text-error)', filterable: true },
  pending: { variant: 'amber', label: 'Pending', color: '#f59e0b', filterable: true },
  running: { variant: 'amber', label: 'Running', color: '#f59e0b', filterable: true },
  redacting: { variant: 'amber', label: 'Redacting', color: '#f59e0b', filterable: false },
  cancelling: { variant: 'amber', label: 'Cancelling...', color: '#f59e0b', filterable: false },
  cancelled: { variant: 'orange', label: 'Cancelled', color: '#f97316', filterable: true },
  info: {
    variant: 'gray',
    label: 'Info',
    color: 'var(--terminal-status-info-color)',
    filterable: true,
  },
}

const TRIGGER_VARIANT_MAP: Record<string, React.ComponentProps<typeof Badge>['variant']> = {
  manual: 'gray-secondary',
  api: 'blue',
  schedule: 'green',
  chat: 'purple',
  webhook: 'orange',
  mcp: 'cyan',
  copilot: 'pink',
  mothership: 'pink',
  workflow: 'blue-secondary',
  custom_block: 'blue-secondary',
}

interface StatusBadgeProps {
  status: RunStatus
}

/**
 * Renders a colored badge indicating log execution status.
 * @param props - Component props containing the status
 * @returns A Badge with dot indicator and status label
 */
export function StatusBadge({ status }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status]
  return React.createElement(
    Badge,
    { variant: config.variant, dot: true, size: 'sm' },
    config.label
  )
}

interface TriggerBadgeProps {
  trigger: TriggerPresentation
}

/**
 * Renders a colored badge indicating the run trigger type. Trigger metadata is
 * resolved by the observability mapper — no block-registry lookups here.
 */
export function TriggerBadge({ trigger }: TriggerBadgeProps) {
  const variant = TRIGGER_VARIANT_MAP[trigger.type] ?? 'gray-secondary'
  return React.createElement(
    Badge,
    { variant, size: 'sm', className: 'whitespace-nowrap' },
    trigger.label
  )
}

/**
 * Format latency value for display in dashboard UI
 * @param ms - Latency in milliseconds (number)
 * @returns Formatted latency string
 */
export function formatLatency(ms: number): string {
  if (!Number.isFinite(ms) || ms <= 0) return '—'
  return formatDuration(ms, { precision: 2 }) ?? '—'
}

export const formatDate = (dateString: string) => {
  const date = new Date(dateString)
  return {
    full: date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    }),
    time: date.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    }),
    formatted: format(date, 'HH:mm:ss'),
    compact: format(date, 'MMM d HH:mm:ss'),
    compactDate: format(date, 'MMM d').toUpperCase(),
    compactTime: format(date, 'h:mm a'),
    relative: formatRelativeTime(dateString),
  }
}
