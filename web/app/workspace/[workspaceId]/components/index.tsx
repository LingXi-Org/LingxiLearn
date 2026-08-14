'use client'

import type { ComponentType, ReactNode } from 'react'
import { Button } from '@sim/emcn'

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

export function IntegrationTabsHeader({ active }: { active?: string; workspaceId?: string }) {
  return (
    <div className='flex h-12 items-center border-b border-[var(--border)] px-6 text-sm text-[var(--text-primary)]'>
      {active === 'skills' ? 'Skills' : '灵犀工作区'}
    </div>
  )
}

export interface ChromeActionSpec {
  text: string
  icon?: ComponentType<{ className?: string }>
  variant?: string
  active?: boolean
}

export interface BreadcrumbItem {
  label: string
  href?: string
  icon?: any
  onClick?: () => void
  terminal?: boolean
}

export function ResourceChromeFallback({
  title,
  searchPlaceholder,
}: {
  icon?: ComponentType<{ className?: string }>
  title?: string
  columns?: unknown[]
  actions?: ChromeActionSpec[]
  breadcrumbs?: BreadcrumbItem[]
  searchPlaceholder?: string
  hasSort?: boolean
  hasFilter?: boolean
}) {
  return (
    <div className='flex h-full flex-col bg-[var(--bg)] p-6'>
      <h1 className='text-base font-medium text-[var(--text-primary)]'>{title ?? '灵犀工作区'}</h1>
      {searchPlaceholder && (
        <p className='mt-2 text-xs text-[var(--text-muted)]'>{searchPlaceholder}</p>
      )}
      <p className='mt-8 text-center text-sm text-[var(--text-muted)]'>未接入</p>
    </div>
  )
}

export function MessageActions(_props: any) {
  return null
}

export function ConversationListItem() {
  return null
}

export function InlineRenameInput() {
  return null
}

export function FloatingOverflowText(_props: any) {
  return null
}

export interface SortConfig {
  column?: string
  direction?: 'asc' | 'desc' | null
  options?: Array<{ id: string; label: string }>
  active?: { column: string; direction: 'asc' | 'desc' } | null
  onSort?: (column: string, direction: 'asc' | 'desc') => void
  onClear?: () => void
}
export interface SelectableConfig {
  selectedIds?: Set<string>
  onToggle?: (id: string) => void
  onSelectRow?: (...args: any[]) => void
  onSelectAll?: (...args: any[]) => void
  isAllSelected?: boolean
  disabled?: boolean
}
export interface ColumnOption {
  id: string
  label: string
  value?: string
  type?: string
  icon?: ComponentType<any>
  color?: string
}
export interface ResourceColumn {
  id?: string
  name?: string
  header?: string
  width?: number
  widthMultiplier?: number
}
export interface ResourceRow {
  id?: string
  [key: string]: unknown
}
export interface ResourceCell {
  value?: unknown
  displayValue?: ReactNode
  content?: ReactNode
  label?: ReactNode
}
export interface ResourceAction {
  label?: string
  text?: string
  icon?: ComponentType<any>
  variant?: string
  onClick?: () => void
  onSelect?: () => void
  disabled?: boolean
}
export interface FilterTag {
  id?: string
  label: string
  value?: string
}

export function FilterTag(_props: FilterTag) {
  return null
}

export function ResourceHeader({ children, ...props }: { children?: ReactNode; [key: string]: any }) {
  return <div className='flex items-center' {...props}>{children}</div>
}

export function ResourceOptions({ children, ...props }: { children?: ReactNode; [key: string]: any }) {
  return <div className='flex items-center gap-2' {...props}>{children}</div>
}

export function ResourceTable({ children, ...props }: { children?: ReactNode; [key: string]: any }) {
  return <div className='min-h-0 flex-1 overflow-auto' {...props}>{children}</div>
}

// Native resource pages use these compound slots. Keeping them on the shared
// resource object preserves the upstream JSX contract while allowing Lingxi to
// render a single-user, non-collaborative shell.
export const Resource = Object.assign(
  function Resource(_props: any) {
    return null
  },
  { Header: ResourceHeader, Options: ResourceOptions, Table: ResourceTable }
)

export function ResourceTile(_props: any) {
  return null
}

export function SkillTile(_props: any) {
  return null
}

export const EMPTY_CELL_PLACEHOLDER = '—'

export { ownerCell } from './resource/components/owner-cell'
export { timeCell } from './resource/components/time-cell'
export { SortDropdown } from './resource/components/resource-options'
