export type TimeRange =
  | 'Past 30 minutes'
  | 'Past hour'
  | 'Past 6 hours'
  | 'Past 12 hours'
  | 'Past 24 hours'
  | 'Past 3 days'
  | 'Past 7 days'
  | 'Past 14 days'
  | 'Past 30 days'
  | 'All time'
  | 'Custom range'

export type LogLevel =
  | 'error'
  | 'info'
  | 'running'
  | 'pending'
  | 'cancelled'
  | 'all'
  | (string & {})

export const CORE_TRIGGER_TYPES = [
  'manual',
  'api',
  'schedule',
  'chat',
  'webhook',
  'mcp',
  'copilot',
  'mothership',
  'workflow',
  'custom_block',
] as const

export type CoreTriggerType = (typeof CORE_TRIGGER_TYPES)[number]
export type TriggerType = CoreTriggerType | 'all' | (string & {})
export type LogViewMode = 'logs' | 'dashboard' | 'trajectory'
