'use client'

import { useMemo } from 'react'
import { ChipCombobox } from '@sim/emcn'

export interface ChunkFilterPanelProps {
  /** Multi-select view of the scalar enabled filter (`[]` = all). */
  enabledFilter: string[]
  /** Filter change — the controller resets the page and clears the selection. */
  onEnabledFilterChange: (values: string[]) => void
}

/**
 * The document detail's chunk status filter popover. Pure presentation; the
 * scalar URL param mapping and selection reset live in the list controller.
 */
export function ChunkFilterPanel({ enabledFilter, onEnabledFilterChange }: ChunkFilterPanelProps) {
  const enabledDisplayLabel = useMemo(() => {
    if (enabledFilter.length === 0) return 'All'
    return enabledFilter[0] === 'enabled' ? 'Enabled' : 'Disabled'
  }, [enabledFilter])

  return (
    <div className='flex w-[240px] flex-col gap-3 p-3'>
      <div className='flex flex-col gap-1.5'>
        <span className='text-[var(--text-secondary)] text-caption'>Status</span>
        <ChipCombobox
          options={[
            { value: 'enabled', label: 'Enabled' },
            { value: 'disabled', label: 'Disabled' },
          ]}
          multiSelect
          multiSelectValues={enabledFilter}
          onMultiSelectChange={onEnabledFilterChange}
          overlayContent={
            <span className='truncate text-[var(--text-primary)]'>{enabledDisplayLabel}</span>
          }
          showAllOption
          allOptionLabel='All'
          className='w-full'
        />
      </div>
      {enabledFilter.length > 0 && (
        <button
          type='button'
          onClick={() => onEnabledFilterChange([])}
          className='flex h-[32px] w-full items-center justify-center rounded-md text-[var(--text-secondary)] text-caption transition-colors hover-hover:bg-[var(--surface-active)]'
        >
          Clear all filters
        </button>
      )}
    </div>
  )
}
