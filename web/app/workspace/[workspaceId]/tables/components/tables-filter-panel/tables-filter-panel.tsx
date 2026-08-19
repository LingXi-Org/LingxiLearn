import type { ComboboxOption } from '@sim/emcn'
import { ChipCombobox } from '@sim/emcn'

export interface TablesFilterPanelProps {
  rowCountFilter: string[]
  ownerFilter: string[]
  memberOptions: ComboboxOption[]
  onRowCountFilterChange: (next: string[]) => void
  onOwnerFilterChange: (next: string[]) => void
}

const ROW_COUNT_OPTIONS = [
  { value: 'empty', label: 'Empty' },
  { value: 'small', label: 'Small (1–100 rows)' },
  { value: 'large', label: 'Large (101+ rows)' },
] as const

const ROW_COUNT_LABELS: Record<string, string> = {
  empty: 'Empty',
  small: 'Small (1–100)',
  large: 'Large (101+)',
}

function rowCountDisplayLabel(rowCountFilter: string[]): string {
  if (rowCountFilter.length === 0) return 'All'
  if (rowCountFilter.length === 1) {
    return ROW_COUNT_LABELS[rowCountFilter[0]] ?? rowCountFilter[0]
  }
  return `${rowCountFilter.length} selected`
}

function ownerDisplayLabel(ownerFilter: string[], memberOptions: ComboboxOption[]): string {
  if (ownerFilter.length === 0) return 'All'
  if (ownerFilter.length === 1) {
    return memberOptions.find((option) => option.value === ownerFilter[0])?.label ?? '1 member'
  }
  return `${ownerFilter.length} members`
}

/**
 * The Tables list filter popover content — row-count buckets and owner multi-selects. Pure
 * presentation: every value and setter arrives via props, so the panel never owns filter
 * state itself.
 */
export function TablesFilterPanel({
  rowCountFilter,
  ownerFilter,
  memberOptions,
  onRowCountFilterChange,
  onOwnerFilterChange,
}: TablesFilterPanelProps) {
  const hasActiveFilters = rowCountFilter.length > 0 || ownerFilter.length > 0

  return (
    <div className='flex w-[240px] flex-col gap-3 p-3'>
      <div className='flex flex-col gap-1.5'>
        <span className='text-[var(--text-secondary)] text-caption'>行数</span>
        <ChipCombobox
          options={[...ROW_COUNT_OPTIONS]}
          multiSelect
          multiSelectValues={rowCountFilter}
          onMultiSelectChange={onRowCountFilterChange}
          overlayContent={
            <span className='truncate text-[var(--text-primary)]'>
              {rowCountDisplayLabel(rowCountFilter)}
            </span>
          }
          showAllOption
          allOptionLabel='All'
          className='w-full'
        />
      </div>
      {memberOptions.length > 0 && (
        <div className='flex flex-col gap-1.5'>
          <span className='text-[var(--text-secondary)] text-caption'>所有者</span>
          <ChipCombobox
            options={memberOptions}
            multiSelect
            multiSelectValues={ownerFilter}
            onMultiSelectChange={onOwnerFilterChange}
            overlayContent={
              <span className='truncate text-[var(--text-primary)]'>
                {ownerDisplayLabel(ownerFilter, memberOptions)}
              </span>
            }
            searchable
            searchPlaceholder='Search members...'
            showAllOption
            allOptionLabel='All'
            className='w-full'
          />
        </div>
      )}
      {hasActiveFilters && (
        <button
          type='button'
          onClick={() => {
            onRowCountFilterChange([])
            onOwnerFilterChange([])
          }}
          className='flex h-[32px] w-full items-center justify-center rounded-md text-[var(--text-secondary)] text-caption transition-colors hover-hover:bg-[var(--surface-active)]'
        >
          Clear all filters
        </button>
      )}
    </div>
  )
}
