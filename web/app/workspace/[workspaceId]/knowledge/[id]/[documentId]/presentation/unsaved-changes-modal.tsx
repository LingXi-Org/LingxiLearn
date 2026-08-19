'use client'

import { ChipConfirmModal } from '@sim/emcn'

interface UnsavedChangesModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onDiscard: () => void
}

/**
 * Guard dialog shown when a route change or editor close would drop unsaved
 * chunk edits.
 */
export function UnsavedChangesModal({ open, onOpenChange, onDiscard }: UnsavedChangesModalProps) {
  return (
    <ChipConfirmModal
      open={open}
      onOpenChange={onOpenChange}
      srTitle='Unsaved Changes'
      title='Unsaved Changes'
      text='You have unsaved changes. Are you sure you want to discard them?'
      dismissLabel='Keep editing'
      confirm={{ label: 'Discard Changes', onClick: onDiscard }}
    />
  )
}
