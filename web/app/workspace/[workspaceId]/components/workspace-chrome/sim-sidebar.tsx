'use client'

import { useEffect, useMemo, useState } from 'react'
import { Chip, ChipLink, cn, Tooltip } from '@sim/emcn'
import {
  Database,
  Files,
  Home,
  List,
  PanelLeft,
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
import { useTablesList } from '@/hooks/queries/tables'
import { useSidebarResize } from '@/app/workspace/[workspaceId]/w/components/sidebar/hooks/use-sidebar-resize'
import { useRegisterGlobalCommands } from '@/app/workspace/[workspaceId]/providers/global-commands-provider'
import { createCommands } from '@/app/workspace/[workspaceId]/utils/commands-utils'
import { useSidebarStore } from '@/stores/sidebar/store'

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

/**
 * Lingxi's resource/task data rendered through Sim's native sidebar chrome.
 * Collapse, width persistence, resize gestures, tooltips, and row geometry all
 * intentionally come from the Sim store/emcn primitives rather than a second
 * Lingxi-specific sidebar implementation.
 */
interface SidebarProps {
  isCollapsed: boolean
  isPeeking?: boolean
}

const resourceItems = [
  { label: '文件', icon: Files, segment: 'files' },
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
  const className = cn(
    'h-[30px] gap-2 text-[12px]',
    collapsed && 'justify-center px-0 [&>span]:hidden',
    disabled && 'cursor-not-allowed opacity-50 hover-hover:bg-transparent'
  )
  const children = !collapsed ? (
    <>
      <span className='min-w-0 truncate'>{label}</span>
      {badge && <span className='shrink-0 text-[10px] text-[var(--text-muted)]'>{badge}</span>}
    </>
  ) : null

  const wrapped =
    href && !disabled ? (
      <ChipLink href={href} leftIcon={Icon} active={active} fullWidth className={className}>
        {children}
      </ChipLink>
    ) : (
      <Chip
        leftIcon={Icon}
        active={active}
        fullWidth
        disabled={disabled}
        title={disabled ? '未接入' : undefined}
        className={className}
      >
        {children}
      </Chip>
    )

  return (
    <SidebarTooltip label={disabled ? `${label}（未接入）` : label} enabled={collapsed}>
      {wrapped}
    </SidebarTooltip>
  )
}

function SidebarEmptyRow({ label }: { label: string }) {
  return (
    <div className='flex h-[30px] items-center gap-2 rounded-lg px-2 text-[12px] text-[var(--text-muted)]'
      aria-live='polite'
    >
      <Task className='size-[16px] shrink-0 opacity-70' />
      <span className='min-w-0 truncate'>{label}</span>
    </div>
  )
}

export function SimSidebar({ isCollapsed, isPeeking = false }: SidebarProps) {
  const params = useParams<{ workspaceId: string }>()
  const pathname = usePathname()
  const workspaceId = params?.workspaceId || 'lingxi'
  const [tasks, setTasks] = useState<AgentTaskListItem[]>([])
  const [loadError, setLoadError] = useState(false)
  const compact = isCollapsed && !isPeeking
  const toggleCollapsed = useSidebarStore((state) => state.toggleCollapsed)
  const { handlePointerDown } = useSidebarResize()
  const { data: tables = [], isError: tablesError } = useTablesList(workspaceId, 'active')

  useRegisterGlobalCommands(() =>
    createCommands([
      {
        id: 'toggle-sidebar',
        handler: () => toggleCollapsed(),
      },
    ])
  )

  useEffect(() => {
    let active = true
    void api
      .agentTasks()
      .then((result) => {
        if (active) {
          setTasks(result.tasks)
          setLoadError(false)
        }
      })
      .catch(() => {
        if (active) setLoadError(true)
      })
    return () => {
      active = false
    }
  }, [pathname])

  const taskRows = useMemo(() => tasks.slice(0, 30), [tasks])
  const tableRows = useMemo(() => tables.slice(0, 30), [tables])

  return (
    <aside
      className='sidebar-container relative flex h-full min-h-0 flex-col overflow-hidden border-r border-[var(--border)] bg-[var(--surface-1)] px-2 pb-2 pt-3'
      data-collapsed={compact || undefined}
      aria-label='工作区侧栏'
    >
      <div className='relative flex h-[30px] shrink-0 items-center gap-1'>
        {compact ? (
          <SidebarTooltip label='展开侧栏' enabled side='right'>
            <Chip
              onClick={toggleCollapsed}
              aria-label='展开侧栏'
              leftAdornment={<PanelLeft className='-scale-x-100 size-4' />}
              className='size-[30px] shrink-0 justify-center px-0'
            />
          </SidebarTooltip>
        ) : (
          <Link
            href={`/workspace/${workspaceId}/home`}
            className='flex h-[30px] min-w-0 flex-1 items-center gap-2 rounded-lg px-2 transition-colors hover-hover:bg-[var(--surface-hover)]'
            aria-label='灵犀智学'
          >
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
          </Link>
        )}
        {!compact && (
          <SidebarTooltip label='收起侧栏' enabled side='bottom' shortcut='Ctrl+B'>
            <Chip
              onClick={toggleCollapsed}
              aria-label='收起侧栏'
              leftAdornment={<PanelLeft className='size-4' />}
              className='size-[30px] shrink-0 justify-center px-0'
            />
          </SidebarTooltip>
        )}
      </div>

      <div
        className={cn(
          'absolute top-0 right-0 bottom-0 z-20 w-2 translate-x-1/2',
          compact ? 'cursor-e-resize' : 'cursor-ew-resize'
        )}
        onPointerDown={compact ? undefined : handlePointerDown}
        onClick={compact ? toggleCollapsed : undefined}
        onKeyDown={
          compact
            ? (event) => {
                if (event.key === 'Enter' || event.key === ' ') toggleCollapsed()
              }
            : undefined
        }
        role={compact ? 'button' : 'separator'}
        tabIndex={0}
        aria-orientation={compact ? undefined : 'vertical'}
        aria-label={compact ? '展开侧栏' : '调整侧栏宽度'}
      />

      <nav className='mt-4 space-y-1' aria-label='主导航'>
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

      <div className='space-y-1'>
        <SidebarRow
          icon={Table}
          label='表格'
          href={`/workspace/${workspaceId}/tables`}
          active={pathname?.includes(`/workspace/${workspaceId}/tables`)}
          collapsed={compact}
        />
        {!compact && (
          <div className='ml-2 space-y-1 border-l border-[var(--border)] pl-2'>
            {tableRows.map((table) => (
              <SidebarRow
                key={table.id}
                icon={Table}
                label={table.name}
                href={`/workspace/${workspaceId}/tables/${table.id}`}
                active={pathname?.includes(`/workspace/${workspaceId}/tables/${table.id}`)}
                collapsed={false}
              />
            ))}
            {tablesError && <SidebarEmptyRow label='表格暂时无法加载' />}
            {!tablesError && tableRows.length === 0 && <SidebarEmptyRow label='暂无表格' />}
          </div>
        )}
      </div>

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
        {loadError && !compact && <SidebarEmptyRow label='任务暂时无法加载' />}
        {!loadError && taskRows.length === 0 && !compact && (
          <SidebarEmptyRow label='暂无学习任务，从首页开始提问' />
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
