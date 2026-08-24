'use client'

import { lazy, type PointerEventHandler, type RefObject, Suspense } from 'react'
import { Button, cn } from '@/components/ui-kit'
import { PanelLeft } from '@/components/ui-kit/icons'
import type { MothershipResource } from '../types'
import { MothershipResourcesProvider } from './mothership-resources-context'
import { RESOURCE_HEADER_CLASSES } from './mothership-view/components/resource-tabs/resource-tab-controls'
import type { MothershipViewProps } from './mothership-view/mothership-view'

const MothershipView = lazy(() =>
  import('./mothership-view/mothership-view').then((module) => ({
    default: module.MothershipView,
  }))
)

interface WorkspaceResourcePanelProps extends Omit<MothershipViewProps, 'className'> {
  panelRef: RefObject<HTMLDivElement | null>
  skipTransition: boolean
  onResizePointerDown: PointerEventHandler<HTMLDivElement>
  onExpand: () => void
  onCollapse: () => void
  onSelect: (resourceId: string) => void
  onAdd: (resource: MothershipResource) => void
  onRemove: MothershipResourceOperations['remove']
  onReorder: MothershipResourceOperations['reorder']
}

interface MothershipResourceOperations {
  remove: (type: MothershipResource['type'], id: string) => void
  reorder: (resources: MothershipResource[]) => void
}

export function WorkspaceResourcePanel({
  panelRef,
  skipTransition,
  onResizePointerDown,
  onExpand,
  onCollapse,
  onSelect,
  onAdd,
  onRemove,
  onReorder,
  ...viewProps
}: WorkspaceResourcePanelProps) {
  return (
    <>
      {!viewProps.isCollapsed && (
        <div className='relative z-20 w-0 flex-none'>
          <div
            className='absolute inset-y-0 left-[-4px] w-[8px] cursor-ew-resize'
            role='separator'
            aria-orientation='vertical'
            aria-label='Resize resource panel'
            onPointerDown={onResizePointerDown}
          />
        </div>
      )}

      <MothershipResourcesProvider
        selectResource={onSelect}
        addResource={onAdd}
        removeResource={onRemove}
        reorderResources={onReorder}
        collapseResource={onCollapse}
      >
        <Suspense fallback={null}>
          <MothershipView
            ref={panelRef}
            {...viewProps}
            className={skipTransition ? '!transition-none' : undefined}
          />
        </Suspense>
      </MothershipResourcesProvider>

      <div
        className={cn(
          'absolute top-0 z-30 flex items-center',
          RESOURCE_HEADER_CLASSES.controls,
          RESOURCE_HEADER_CLASSES.endPosition
        )}
      >
        <Button
          variant='ghost'
          size={null}
          type='button'
          onClick={viewProps.isCollapsed ? onExpand : onCollapse}
          className='size-[30px] rounded-[8px] hover-hover:bg-[var(--surface-active)]'
          aria-label={viewProps.isCollapsed ? 'Expand resource view' : 'Collapse resource view'}
        >
          <span className='relative'>
            <PanelLeft className='-scale-x-100 size-[16px] text-[var(--text-icon)]' />
            {viewProps.isCollapsed && (viewProps.activityResourceIds?.size ?? 0) > 0 && (
              <span className='-top-0.5 -right-0.5 absolute size-1.5 rounded-full bg-[var(--brand-primary)]' />
            )}
          </span>
        </Button>
      </div>
    </>
  )
}
