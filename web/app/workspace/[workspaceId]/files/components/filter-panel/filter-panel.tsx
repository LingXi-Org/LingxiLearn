'use client'

import { Button, ChipCombobox, type ComboboxOption } from '@sim/emcn'
import type { WorkspaceMember } from '@/hooks/queries/workspace'

export interface FilesFilterPanelProps {
  typeFilter: string[]
  sizeFilter: string[]
  uploadedByFilter: string[]
  /** Workspace members as selectable options for the uploader filter. */
  memberOptions: ComboboxOption[]
  membersById: Map<string, WorkspaceMember>
  onTypeChange: (next: string[]) => void
  onSizeChange: (next: string[]) => void
  onUploadedByChange: (next: string[]) => void
  onClearAll: () => void
}

const TYPE_FILTER_OPTIONS = [
  { value: 'document', label: 'Documents' },
  { value: 'image', label: 'Images' },
  { value: 'audio', label: 'Audio' },
  { value: 'video', label: 'Video' },
] as const

const SIZE_FILTER_OPTIONS = [
  { value: 'small', label: 'Small (< 1 MB)' },
  { value: 'medium', label: 'Medium (1–10 MB)' },
  { value: 'large', label: 'Large (> 10 MB)' },
] as const

const TYPE_LABELS: Record<string, string> = {
  document: 'Documents',
  image: 'Images',
  audio: 'Audio',
  video: 'Video',
}

const SIZE_LABELS: Record<string, string> = {
  small: 'Small',
  medium: 'Medium',
  large: 'Large',
}

/**
 * The Files list's filter popover body: file type, size bucket, and uploader multi-selects,
 * plus a clear-all affordance while any filter is active. Pure presentation — filter values
 * and their setters come from the list's URL-backed filter controller.
 */
export function FilesFilterPanel({
  typeFilter,
  sizeFilter,
  uploadedByFilter,
  memberOptions,
  membersById,
  onTypeChange,
  onSizeChange,
  onUploadedByChange,
  onClearAll,
}: FilesFilterPanelProps) {
  const typeDisplayLabel =
    typeFilter.length === 0
      ? 'All'
      : typeFilter.length === 1
        ? (TYPE_LABELS[typeFilter[0]] ?? typeFilter[0])
        : `${typeFilter.length} selected`

  const sizeDisplayLabel =
    sizeFilter.length === 0
      ? 'All'
      : sizeFilter.length === 1
        ? (SIZE_LABELS[sizeFilter[0]] ?? sizeFilter[0])
        : `${sizeFilter.length} selected`

  const uploadedByDisplayLabel =
    uploadedByFilter.length === 0
      ? 'All'
      : uploadedByFilter.length === 1
        ? (membersById.get(uploadedByFilter[0])?.name ?? '1 member')
        : `${uploadedByFilter.length} members`

  const hasActiveFilters =
    typeFilter.length > 0 || sizeFilter.length > 0 || uploadedByFilter.length > 0

  return (
    <div className='flex w-[240px] flex-col gap-3 p-3'>
      <div className='flex flex-col gap-1.5'>
        <span className='text-[var(--text-secondary)] text-caption'>File Type</span>
        <ChipCombobox
          options={[...TYPE_FILTER_OPTIONS]}
          multiSelect
          multiSelectValues={typeFilter}
          onMultiSelectChange={onTypeChange}
          overlayContent={
            <span className='truncate text-[var(--text-primary)]'>{typeDisplayLabel}</span>
          }
          showAllOption
          allOptionLabel='All'
          className='w-full'
        />
      </div>
      <div className='flex flex-col gap-1.5'>
        <span className='text-[var(--text-secondary)] text-caption'>Size</span>
        <ChipCombobox
          options={[...SIZE_FILTER_OPTIONS]}
          multiSelect
          multiSelectValues={sizeFilter}
          onMultiSelectChange={onSizeChange}
          overlayContent={
            <span className='truncate text-[var(--text-primary)]'>{sizeDisplayLabel}</span>
          }
          showAllOption
          allOptionLabel='All'
          className='w-full'
        />
      </div>
      {memberOptions.length > 0 && (
        <div className='flex flex-col gap-1.5'>
          <span className='text-[var(--text-secondary)] text-caption'>Uploaded By</span>
          <ChipCombobox
            options={memberOptions}
            multiSelect
            multiSelectValues={uploadedByFilter}
            onMultiSelectChange={onUploadedByChange}
            overlayContent={
              <span className='truncate text-[var(--text-primary)]'>{uploadedByDisplayLabel}</span>
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
        <Button
          variant='ghost'
          onClick={onClearAll}
          className='h-[32px] w-full text-caption hover-hover:bg-[var(--surface-active)]'
        >
          Clear all filters
        </Button>
      )}
    </div>
  )
}
