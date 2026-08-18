import { useMemo } from 'react'
import type { ChipDropdownOption } from '@sim/emcn'
import { Button, ChipDropdown } from '@sim/emcn'
import type { WorkspaceMember } from '@/hooks/queries/workspace'
import type { KnowledgeListFilters } from '../list/types'

export const CONNECTOR_FILTER_OPTIONS: ChipDropdownOption[] = [
  { value: 'all', label: 'All' },
  { value: 'connected', label: 'With connectors' },
  { value: 'unconnected', label: 'Without connectors' },
]

export const CONTENT_FILTER_OPTIONS: ChipDropdownOption[] = [
  { value: 'all', label: 'All' },
  { value: 'has-docs', label: 'Has documents' },
  { value: 'empty', label: 'Empty' },
]

const FILTER_SECTION_LABEL_CLASS = 'text-[var(--text-muted)] text-small'

const CLEAR_BUTTON_CLASS =
  '-mr-1 h-auto px-1 py-0.5 text-[var(--text-muted)] text-xs hover-hover:text-[var(--text-secondary)]'

interface FilterSectionProps {
  label: string
  hasValue: boolean
  onClear: () => void
  children: React.ReactNode
}

function FilterSection({ label, hasValue, onClear, children }: FilterSectionProps) {
  return (
    <div className='flex flex-col gap-2'>
      <div className='flex h-5 items-center justify-between'>
        <span className={FILTER_SECTION_LABEL_CLASS}>{label}</span>
        {hasValue && (
          <Button variant='ghost' onClick={onClear} className={CLEAR_BUTTON_CLASS}>
            Clear
          </Button>
        )}
      </div>
      {children}
    </div>
  )
}

export interface KnowledgeFilterPanelProps {
  filters: KnowledgeListFilters
  members: WorkspaceMember[] | undefined
  onConnectorChange: (next: string[]) => void
  onContentChange: (next: string[]) => void
  onOwnerChange: (next: string[]) => void
}

/**
 * The structured filter popover content for the knowledge list: connector presence,
 * document presence, and owner. Purely presentational — every value and setter arrives
 * from the URL state hook.
 */
export function KnowledgeFilterPanel({
  filters,
  members,
  onConnectorChange,
  onContentChange,
  onOwnerChange,
}: KnowledgeFilterPanelProps) {
  const memberOptions: ChipDropdownOption[] = useMemo(
    () =>
      (members ?? []).map((m) => ({
        value: m.userId,
        label: m.name,
        iconElement: m.image ? (
          <img
            src={m.image}
            alt={m.name}
            referrerPolicy='no-referrer'
            className='size-[14px] rounded-full border border-[var(--border)] object-cover'
          />
        ) : (
          <span className='flex size-[14px] items-center justify-center rounded-full border border-[var(--border)] bg-[var(--surface-3)] font-medium text-[8px] text-[var(--text-secondary)]'>
            {m.name.charAt(0).toUpperCase()}
          </span>
        ),
      })),
    [members]
  )

  return (
    <div className='flex w-[260px] flex-col gap-3 p-3'>
      <FilterSection
        label='Connectors'
        hasValue={filters.connector.length > 0}
        onClear={() => onConnectorChange([])}
      >
        <ChipDropdown
          options={CONNECTOR_FILTER_OPTIONS}
          value={filters.connector[0] ?? 'all'}
          onChange={(value) => onConnectorChange(value === 'all' ? [] : [value])}
          align='start'
          fullWidth
        />
      </FilterSection>
      <FilterSection
        label='Content'
        hasValue={filters.content.length > 0}
        onClear={() => onContentChange([])}
      >
        <ChipDropdown
          options={CONTENT_FILTER_OPTIONS}
          value={filters.content[0] ?? 'all'}
          onChange={(value) => onContentChange(value === 'all' ? [] : [value])}
          align='start'
          fullWidth
        />
      </FilterSection>
      {memberOptions.length > 0 && (
        <FilterSection
          label='Owner'
          hasValue={filters.owner.length > 0}
          onClear={() => onOwnerChange([])}
        >
          <ChipDropdown
            multiple
            options={memberOptions}
            value={filters.owner}
            onChange={onOwnerChange}
            allLabel='All'
            searchable
            searchPlaceholder='Search members...'
            align='start'
            fullWidth
          />
        </FilterSection>
      )}
    </div>
  )
}
