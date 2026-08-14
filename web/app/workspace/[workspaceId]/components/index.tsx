'use client'

import type { ComponentType, ReactNode } from 'react'
import { Button } from '@sim/emcn'

export { ConversationListItem } from './conversation-list-item'
export { InlineRenameInput } from './inline-rename-input'
export { IntegrationTabsHeader } from './integration-tabs-header'
export { MessageActions } from './message-actions'
export { FloatingOverflowText } from './resource/components/floating-overflow-text'
export { ResourceChromeFallback } from './resource/components/resource-chrome-fallback'
export {
  EMPTY_CELL_PLACEHOLDER,
  Resource,
  type PaginationConfig,
  type ResourceCell,
  type ResourceCellEditing,
  type ResourceColumn,
  type ResourceRow,
  type ResourceTableHandle,
  type RowDragDropConfig,
  type SelectableConfig,
} from './resource/resource'
export { ResourceTile } from './resource-tile'
export { SkillTile } from './skill-tile'
export type {
  BreadcrumbEditing,
  BreadcrumbItem,
  DropdownOption,
  ResourceAction,
} from './resource/components/resource-header'
export type {
  ColumnOption,
  FilterConfig,
  FilterTag,
  SearchConfig,
  SearchTag,
  SortConfig,
} from './resource/components/resource-options'

/** Lightweight compatibility exports for copied Sim route boundaries. */
export interface ErrorBoundaryProps {
  error: Error & { digest?: string }
  reset: () => void
}

export interface ErrorStateProps extends ErrorBoundaryProps {
  title: string
  description: string
  loggerName: string
  icon?: ReactNode
  children?: ReactNode
}

export function ErrorShell({
  title,
  description,
  children,
}: {
  title: string
  description: string
  icon?: ReactNode
  children: ReactNode
}) {
  return (
    <div className='flex h-full min-h-[320px] items-center justify-center bg-[var(--bg)] p-8 text-center'>
      <div className='max-w-md'>
        <h2 className='text-lg font-medium text-[var(--text-primary)]'>{title}</h2>
        <p className='mt-2 text-sm text-[var(--text-muted)]'>{description}</p>
        <div className='mt-5 flex justify-center gap-2'>{children}</div>
      </div>
    </div>
  )
}

export function ErrorState({ title, description, reset, children }: ErrorStateProps) {
  return (
    <ErrorShell title={title} description={description}>
      {children}
      <Button type='button' variant='primary' size='md' onClick={reset}>
        刷新
      </Button>
    </ErrorShell>
  )
}

export interface ChromeActionSpec {
  text: string
  icon?: ComponentType<{ className?: string }>
  variant?: string
  active?: boolean
}
