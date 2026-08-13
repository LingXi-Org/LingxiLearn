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
  icon?: ComponentType<{ className?: string }>
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

export function MessageActions() {
  return null
}

export function ConversationListItem() {
  return null
}

export function InlineRenameInput() {
  return null
}

export function FloatingOverflowText() {
  return null
}

export function Resource() {
  return null
}

export function ResourceTile() {
  return null
}

export function SkillTile() {
  return null
}

export const EMPTY_CELL_PLACEHOLDER = '—'
