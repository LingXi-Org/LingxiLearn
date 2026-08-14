'use client'

import { useEffect, useMemo, useState } from 'react'
import { Chip, ChipLink, cn, Tooltip } from '@sim/emcn'
import {
  Database,
  Files,
  Home,
  List,
  Search,
  Settings,
  Sparkles,
  Table,
  Task,
} from '@sim/emcn/icons'
import Link from 'next/link'
import { useParams, usePathname } from 'next/navigation'
import { LINGXI_BRAND_ASSETS } from '@/lib/branding/lingxi-assets'
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

const resourceItems = [
  { label: '文件', icon: Files, segment: 'files' },
  { label: '表格', icon: Table, segment: 'tables' },
  { label: '知识库', icon: Database, segment: 'knowledge' },
  { label: '日志', icon: List, segment: 'logs' },
  { label: 'Skills', icon: Sparkles, segment: 'skills' },
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
  const rowClassName = cn(
    'h-[30px] min-w-0 rounded-lg',
    collapsed && 'justify-center px-0 [&>span]:hidden',
    badge && !collapsed && 'pr-1'
  )

  const wrapped =
    href && !disabled ? (
      <ChipLink href={href} leftIcon={Icon} active={active} fullWidth className={rowClassName}>
        {!collapsed && <span className='min-w-0 truncate'>{label}</span>}
        {!collapsed && badge && (
          <span className='ml-auto shrink-0 text-[10px] text-[var(--text-muted)]'>{badge}</span>
        )}
      </ChipLink>
    ) : (
      <Chip
        leftIcon={Icon}
        active={active}
        fullWidth
        disabled={disabled}
        className={rowClassName}
        title={disabled ? '未接入' : undefined}
      >
        {!collapsed && <span className='min-w-0 truncate'>{label}</span>}
      </Chip>
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
    <aside className='sidebar-container flex h-full min-h-0 w-full min-w-0 flex-col border-r border-[var(--border)] bg-[var(--surface-1)] px-2 pb-2 pt-3'>
      <Link
        href={`/workspace/${workspaceId}/home`}
        className={cn(
          'mb-4 flex h-[30px] min-w-0 items-center gap-2 rounded-lg px-2 transition-colors hover-hover:bg-[var(--surface-hover)]',
          compact && 'justify-center px-0'
        )}
        aria-label='灵犀智学'
      >
        {compact ? (
          <>
            <img
              src={LINGXI_BRAND_ASSETS.iconOnLight}
              alt='灵犀智学'
              className='size-[22px] shrink-0 object-contain dark:hidden'
            />
            <img
              src={LINGXI_BRAND_ASSETS.iconOnDark}
              alt=''
              aria-hidden='true'
              className='hidden size-[22px] shrink-0 object-contain dark:block'
            />
          </>
        ) : (
          <>
            <img
              src={LINGXI_BRAND_ASSETS.iconOnLight}
              alt=''
              aria-hidden='true'
              className='size-[22px] shrink-0 object-contain dark:hidden'
            />
            <img
              src={LINGXI_BRAND_ASSETS.iconOnDark}
              alt=''
              aria-hidden='true'
              className='hidden size-[22px] shrink-0 object-contain dark:block'
            />
            <img
              src={LINGXI_BRAND_ASSETS.wordmarkOnLight}
              alt='灵犀智学'
              className='h-[22px] w-auto max-w-[148px] shrink-0 object-contain object-left dark:hidden'
            />
            <img
              src={LINGXI_BRAND_ASSETS.wordmarkOnDark}
              alt=''
              aria-hidden='true'
              className='hidden h-[22px] w-auto max-w-[148px] shrink-0 object-contain object-left dark:block'
            />
          </>
        )}
      </Link>

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
        {resourceItems.map(({ label, icon, segment }) => (
          <SidebarRow
            key={label}
            icon={icon}
            label={label}
            href={`/workspace/${workspaceId}/${segment}`}
            active={pathname?.includes(`/workspace/${workspaceId}/${segment}`)}
            collapsed={compact}
          />
        ))}
        <SidebarRow
          icon={Settings}
          label='设置'
          href={`/workspace/${workspaceId}/settings`}
          active={pathname?.includes(`/workspace/${workspaceId}/settings`)}
          collapsed={compact}
        />
      </div>
    </aside>
  )
}
