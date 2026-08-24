export type {
  CoreTriggerType,
  LogLevel,
  LogViewMode,
  TimeRange,
  TriggerType,
} from '@/lib/logs/filter-types'
export { CORE_TRIGGER_TYPES } from '@/lib/logs/filter-types'

import type { LogViewMode } from '@/lib/logs/filter-types'

/**
 * Non-URL logs view state. The filter state itself (time range, level,
 * workflows, folders, triggers, search) lives in the URL via nuqs
 * (`useLogFilters`); only the selected view is kept in this store.
 */
export interface LogViewState {
  viewMode: LogViewMode
  setViewMode: (viewMode: LogViewMode) => void
}
