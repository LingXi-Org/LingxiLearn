'use client'

import { useEffect, useMemo, useState } from 'react'
import { cn, Tooltip } from '@sim/emcn'
import {
  Database,
  Files,
  Home,
  Integration,
  Search,
  Settings,
  Table,
  Task,
  Workflow,
} from '@sim/emcn/icons'
import Link from 'next/link'
import { useParams, usePathname } from 'next/navigation'
import { api } from '@/lib/lingxi/api'
import type { AgentTaskListItem } from '@/lib/lingxi/types'

export function SidebarTooltip({
  children,
  label,
  enabled,
  side = 'right',
  shortcut,
}: {
  children: React.ReactElement
  label: string
  enabled: boolean
  side?: 'right' | 'bottom'
  shortcut?: string
}) {
  if (!enabled) return children
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>{children}</Tooltip.Trigger>
      <Tooltip.Content side={side}>
        {shortcut ? <Tooltip.Shortcut keys={shortcut}>{label}</Tooltip.Shortcut> : <p>{label}</p>}
      </Tooltip.Content>
    </Tooltip.Root>
  )
}

interface SidebarProps {
  isCollapsed: boolean
  isPeeking?: boolean
}

const unsupportedItems = [
  { label: '文件', icon: Files },
  { label: '表格', icon: Table },
  { label: '知识库', icon: Database },
  { label: '集成', icon: Integration },
  { label: '工作流', icon: Workflow },
]

function formatTaskName(task: AgentTaskListItem): string {
  const name = task.intent.topic?.trim() || task.prompt.trim()
  return name || '未命名任务'
}

function statusLabel(status: AgentTaskListItem['status']): string {
  if (status === 'queued' || status === 'running') return '进行中'
  if (status === 'awaiting_user') return '等待回复'
  if (status === 'failed') return '失败'
  return '已完成'
}

function SidebarRow({
  icon: Icon,
  label,
  href,
  active,
  collapsed,
  disabled = false,
  badge,
}: {
  icon: typeof Home
  label: string
  href?: string
  active?: boolean
  collapsed: boolean
  disabled?: boolean
  badge?: string
}) {
  const content = (
    <span
      className={cn(
        'group flex h-[30px] w-full items-center gap-2 rounded-[6px] px-2 text-[12px] transition-colors',
        collapsed && 'justify-center px-0',
        active
          ? 'bg-[var(--surface-active)] text-[var(--text-primary)]'
          : 'text-[var(--text-secondary)] hover-hover:bg-[var(--surface-hover)] hover-hover:text-[var(--text-primary)]',
        disabled &&
          'cursor-not-allowed opacity-50 hover-hover:bg-transparent hover-hover:text-[var(--text-secondary)]'
      )}
      aria-disabled={disabled || undefined}
      title={disabled ? '未接入' : undefined}
    >
      <Icon className='size-[16px] shrink-0' />
      {!collapsed && <span className='min-w-0 flex-1 truncate'>{label}</span>}
      {!collapsed && badge && (
        <span className='shrink-0 text-[10px] text-[var(--text-muted)]'>{badge}</span>
      )}
    </span>
  )

  const wrapped =
    href && !disabled ? (
      <Link href={href}>{content}</Link>
    ) : (
      <button type='button' className='w-full' disabled={disabled}>
        {content}
      </button>
    )

  return (
    <SidebarTooltip label={disabled ? `${label}（未接入）` : label} enabled={collapsed}>
      {wrapped}
    </SidebarTooltip>
  )
}

export function Sidebar({ isCollapsed, isPeeking = false }: SidebarProps) {
  const params = useParams<{ workspaceId: string }>()
  const pathname = usePathname()
  const workspaceId = params?.workspaceId || 'lingxi'
  const [tasks, setTasks] = useState<AgentTaskListItem[]>([])
  const [loadError, setLoadError] = useState(false)
  const compact = isCollapsed && !isPeeking

  useEffect(() => {
    let active = true
    void api
      .agentTasks()
      .then((result) => {
        if (active) setTasks(result.tasks)
      })
      .catch(() => {
        if (active) setLoadError(true)
      })
    return () => {
      active = false
    }
  }, [pathname])

  const taskRows = useMemo(() => tasks.slice(0, 30), [tasks])

  return (
    <aside className='flex h-full min-h-0 w-[var(--sidebar-width)] flex-col border-r border-[var(--border)] bg-[var(--surface-1)] px-2 pb-2 pt-3'>
      <div className={cn('mb-4 flex items-center gap-2 px-2', compact && 'justify-center px-0')}>
        <div className='flex size-[24px] shrink-0 items-center justify-center rounded-[7px] bg-[var(--text-primary)] text-[11px] font-semibold text-[var(--text-inverse)]'>
          灵
        </div>
        {!compact && (
          <span className='truncate text-[13px] font-medium text-[var(--text-primary)]'>灵犀智学</span>
        )}
      </div>

      <nav className='space-y-1' aria-label='主导航'>
        <SidebarRow
          icon={Home}
          label='首页'
          href={`/workspace/${workspaceId}/home`}
          active={pathname?.endsWith('/home') || pathname === `/workspace/${workspaceId}`}
          collapsed={compact}
        />
        <SidebarRow icon={Search} label='搜索' collapsed={compact} disabled />
      </nav>

      <div className='my-4 h-px bg-[var(--border)]' />

      {!compact && (
        <div className='px-2 pb-2 text-[10px] font-medium uppercase tracking-[0.08em] text-[var(--text-muted)]'>
          学习任务
        </div>
      )}
      <div className='min-h-0 flex-1 space-y-1 overflow-y-auto'>
        {taskRows.map((task) => (
          <SidebarRow
            key={task.id}
            icon={Task}
            label={formatTaskName(task)}
            href={`/workspace/${workspaceId}/chat/${task.id}`}
            active={pathname?.includes(`/chat/${task.id}`)}
            collapsed={compact}
            badge={!compact ? statusLabel(task.status) : undefined}
          />
        ))}
        {loadError && !compact && (
          <p className='px-2 py-3 text-[11px] text-[var(--text-muted)]'>任务暂时无法加载</p>
        )}
        {!loadError && taskRows.length === 0 && !compact && (
          <p className='px-2 py-3 text-[11px] leading-5 text-[var(--text-muted)]'>
            还没有学习任务
            <br />
            从首页开始提问
          </p>
        )}
      </div>

      <div className='mt-3 space-y-1 border-t border-[var(--border)] pt-3'>
        {unsupportedItems.map(({ label, icon }) => (
          <SidebarRow key={label} icon={icon} label={label} collapsed={compact} disabled />
        ))}
        <SidebarRow icon={Settings} label='设置' collapsed={compact} disabled />
      </div>
    </aside>
  )
}
