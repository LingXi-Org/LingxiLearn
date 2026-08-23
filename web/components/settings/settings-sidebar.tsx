'use client'

import { useEffect, useRef, useState } from 'react'
import { Chip, ChipConfirmModal, cn, Tooltip } from '@/components/ui-kit'
import { ChevronLeft } from '@/components/ui-kit/icons'
import { useRouter } from 'next/navigation'
import {
  SETTINGS_PLANE_CHROME,
  type SettingsNavigationItem,
  type SettingsSection,
  type StandaloneSettingsPlane,
} from '@/components/settings/navigation'
import { LingxiWordmark } from '@/app/(landing)/components/navbar/components'
import { useSettingsDirtyStore } from '@/stores/settings/dirty/store'

/**
 * The marketing landing page. `?home` is required: the proxy bounces a
 * signed-in user off `/` to `/workspace` unless the param is present.
 */
const LANDING_HREF = '/?home'

/** Where the Back chip goes on planes that don't show the wordmark. */
const WORKSPACE_HREF = '/workspace'

interface SettingsNavigationGroup {
  key: string
  title: string
}

interface SidebarSettingsItem<Section extends SettingsSection>
  extends SettingsNavigationItem<Section> {
  locked?: boolean
}

interface SettingsSidebarProps<Section extends SettingsSection> {
  activeSection: string
  plane: StandaloneSettingsPlane
  groups: readonly SettingsNavigationGroup[]
  hrefForSection: (section: Section) => string
  items: readonly SidebarSettingsItem<Section>[]
  isCollapsed?: boolean
  showCollapsedTooltips?: boolean
}

function SidebarTooltip({
  children,
  label,
  enabled,
}: {
  children: React.ReactElement
  label: string
  enabled: boolean
}) {
  if (!enabled) return children
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>{children}</Tooltip.Trigger>
      <Tooltip.Content side='right'>{label}</Tooltip.Content>
    </Tooltip.Root>
  )
}

export function SettingsSidebar<Section extends SettingsSection>({
  activeSection,
  plane,
  groups,
  hrefForSection,
  items,
  isCollapsed = false,
  showCollapsedTooltips = false,
}: SettingsSidebarProps<Section>) {
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const scrollContentRef = useRef<HTMLDivElement>(null)
  const router = useRouter()

  const requestLeave = useSettingsDirtyStore((state) => state.requestLeave)
  const confirmLeave = useSettingsDirtyStore((state) => state.confirmLeave)
  const cancelLeave = useSettingsDirtyStore((state) => state.cancelLeave)
  const pendingLeave = useSettingsDirtyStore((state) => state.pendingLeave)
  const [hasOverflowTop, setHasOverflowTop] = useState(false)

  useEffect(() => {
    const container = scrollContainerRef.current
    if (!container) return
    const updateScrollState = () => setHasOverflowTop(container.scrollTop > 1)
    updateScrollState()
    container.addEventListener('scroll', updateScrollState, { passive: true })
    const observer = new ResizeObserver(updateScrollState)
    observer.observe(container)
    if (scrollContentRef.current) observer.observe(scrollContentRef.current)
    return () => {
      container.removeEventListener('scroll', updateScrollState)
      observer.disconnect()
    }
  }, [isCollapsed])

  return (
    <>
      <div className='flex flex-shrink-0 flex-col gap-0.5 px-2 pb-1.5'>
        {/* Both stay buttons, not Links: leaving settings must run the unsaved-changes guard. */}
        {SETTINGS_PLANE_CHROME[plane].showWordmark ? (
          <button
            type='button'
            aria-label='灵犀智学首页'
            onClick={() => requestLeave(() => router.push(LANDING_HREF))}
            className='flex h-[30px] flex-shrink-0 items-center px-2 transition-opacity hover:opacity-70'
          >
            <LingxiWordmark />
          </button>
        ) : (
          <SidebarTooltip label='返回' enabled={showCollapsedTooltips}>
            <Chip
              onClick={() => requestLeave(() => router.push(WORKSPACE_HREF))}
              leftIcon={ChevronLeft}
              className='w-full justify-start'
            >
              <span className='sidebar-collapse-hide truncate text-[var(--text-body)]'>返回</span>
            </Chip>
          </SidebarTooltip>
        )}
      </div>

      <div
        ref={isCollapsed ? undefined : scrollContainerRef}
        className={cn(
          'flex flex-1 flex-col overflow-y-auto overflow-x-hidden border-t pt-1.5 pb-2 transition-colors duration-150',
          !hasOverflowTop && 'border-transparent'
        )}
      >
        <div ref={scrollContentRef} className='flex flex-col'>
          {groups
            .map((group) => ({
              ...group,
              items: items.filter((item) => item.group === group.key),
            }))
            .filter((group) => group.items.length > 0)
            .map((group, index) => (
              <div
                key={group.key}
                className={cn(index > 0 && 'mt-6', 'flex flex-shrink-0 flex-col')}
              >
                <div className='px-4 pb-2'>
                  <div className='text-[var(--text-muted)] text-small'>{group.title}</div>
                </div>
                <div className='flex flex-col gap-0.5 px-2'>
                  {group.items.map((item) => {
                    const Icon = item.icon
                    const active = activeSection === item.id
                    return (
                      <SidebarTooltip
                        key={item.id}
                        label={item.label}
                        enabled={showCollapsedTooltips}
                      >
                        <Chip
                          active={active}
                          fullWidth
                          leftIcon={Icon}
                          className='h-[30px] text-[12px]'
                          onClick={() => {
                            if (active) return
                            requestLeave(() => {
                              router.replace(hrefForSection(item.id), { scroll: false })
                            })
                          }}
                        >
                          <span className='sidebar-collapse-hide min-w-0 truncate text-[var(--text-body)]'>
                            {item.label}
                          </span>
                          {item.locked && (
                            <span className='sidebar-collapse-hide ml-auto shrink-0 rounded-[3px] bg-[var(--surface-5)] px-1 py-[1px] font-medium text-[var(--text-icon)] text-micro uppercase tracking-wide'>
                              套餐
                            </span>
                          )}
                        </Chip>
                      </SidebarTooltip>
                    )
                  })}
                </div>
              </div>
            ))}
        </div>
      </div>

      <ChipConfirmModal
        open={pendingLeave !== null}
        onOpenChange={(open) => !open && cancelLeave()}
        srTitle='未保存的更改'
        title='未保存的更改'
        text='你有未保存的更改，确定要放弃吗？'
        dismissLabel='继续编辑'
        confirm={{ label: '放弃更改', onClick: confirmLeave }}
      />
    </>
  )
}
