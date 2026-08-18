'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { SelectableConfig } from '@/app/workspace/[workspaceId]/components'
import { parseFilesRowId } from '@/app/workspace/[workspaceId]/files/lib/file-row-ids'

export interface UseFilesSelectionKeyboardOptions {
  /** List shortcuts only apply while no file is open on the detail route. */
  enabled: boolean
  /** An active inline rename owns the keyboard; the list must not steal Delete/Escape. */
  inlineRenameActive: boolean
  onDelete: () => void
}

/**
 * The Files list's selection controller: checkbox state with shift-click ranges, a
 * select-all bound to the visible rows, pruning when rows disappear, and the list-level
 * keyboard shortcuts (Delete, Escape, Ctrl/Cmd-A).
 */
export function useFilesSelection(
  visibleRowIds: string[],
  keyboard?: UseFilesSelectionKeyboardOptions
) {
  const [selectedRowIds, setSelectedRowIds] = useState<Set<string>>(() => new Set())
  const lastSelectedIndexRef = useRef<number>(-1)

  // Drop selection entries whose rows left the list (filter, folder change, archive).
  const prevVisibleRowIdsRef = useRef(visibleRowIds)
  useEffect(() => {
    if (prevVisibleRowIdsRef.current === visibleRowIds) return
    prevVisibleRowIdsRef.current = visibleRowIds
    lastSelectedIndexRef.current = -1
    const visible = new Set(visibleRowIds)
    setSelectedRowIds((prev) => {
      if (prev.size === 0) return prev
      const next = new Set(Array.from(prev).filter((id) => visible.has(id)))
      return next.size === prev.size ? prev : next
    })
  }, [visibleRowIds])

  const isAllSelected =
    visibleRowIds.length > 0 && visibleRowIds.every((id) => selectedRowIds.has(id))

  const { selectedFileIds, selectedFolderIds } = useMemo(() => {
    const fileIds: string[] = []
    const folderIds: string[] = []
    for (const rowId of selectedRowIds) {
      const item = parseFilesRowId(rowId)
      if (item.kind === 'file') fileIds.push(item.id)
      else folderIds.push(item.id)
    }
    return { selectedFileIds: fileIds, selectedFolderIds: folderIds }
  }, [selectedRowIds])

  const clearSelection = useCallback(() => setSelectedRowIds(new Set()), [])

  const selectOnly = useCallback((rowId: string, index: number) => {
    lastSelectedIndexRef.current = index
    setSelectedRowIds(new Set([rowId]))
  }, [])

  const selectableConfig = useMemo<SelectableConfig>(
    () => ({
      selectedIds: selectedRowIds,
      isAllSelected,
      onSelectRow: (rowId: string, checked: boolean, shiftKey?: boolean) => {
        const currentIndex = visibleRowIds.indexOf(rowId)
        if (shiftKey && lastSelectedIndexRef.current !== -1 && currentIndex !== -1) {
          const start = Math.min(lastSelectedIndexRef.current, currentIndex)
          const end = Math.max(lastSelectedIndexRef.current, currentIndex)
          setSelectedRowIds((prev) => {
            const next = new Set(prev)
            for (let i = start; i <= end; i++) next.add(visibleRowIds[i])
            return next
          })
          lastSelectedIndexRef.current = currentIndex
        } else {
          setSelectedRowIds((prev) => {
            const next = new Set(prev)
            if (checked) next.add(rowId)
            else next.delete(rowId)
            return next
          })
          if (checked) lastSelectedIndexRef.current = currentIndex
          else lastSelectedIndexRef.current = -1
        }
      },
      onSelectAll: (checked: boolean) => {
        lastSelectedIndexRef.current = -1
        setSelectedRowIds((prev) => {
          const next = new Set(prev)
          for (const rowId of visibleRowIds) {
            if (checked) next.add(rowId)
            else next.delete(rowId)
          }
          return next
        })
      },
      disabled: false,
    }),
    [selectedRowIds, isAllSelected, visibleRowIds]
  )

  const selectedRowIdsRef = useRef(selectedRowIds)
  selectedRowIdsRef.current = selectedRowIds
  const visibleRowIdsRef = useRef(visibleRowIds)
  visibleRowIdsRef.current = visibleRowIds
  const keyboardRef = useRef(keyboard)
  keyboardRef.current = keyboard

  useEffect(() => {
    const handleListKeyDown = (e: KeyboardEvent) => {
      const options = keyboardRef.current
      if (!options?.enabled) return
      const active = document.activeElement
      if (
        active &&
        (active.tagName === 'INPUT' ||
          active.tagName === 'TEXTAREA' ||
          (active as HTMLElement).isContentEditable)
      )
        return
      if (options.inlineRenameActive) return

      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedRowIdsRef.current.size > 0) {
        e.preventDefault()
        options.onDelete()
        return
      }

      if (e.key === 'Escape' && selectedRowIdsRef.current.size > 0) {
        e.preventDefault()
        setSelectedRowIds(new Set())
        return
      }

      if ((e.metaKey || e.ctrlKey) && e.key === 'a' && visibleRowIdsRef.current.length > 0) {
        e.preventDefault()
        setSelectedRowIds(new Set(visibleRowIdsRef.current))
      }
    }
    window.addEventListener('keydown', handleListKeyDown)
    return () => window.removeEventListener('keydown', handleListKeyDown)
  }, [])

  return {
    selectedRowIds,
    setSelectedRowIds,
    isAllSelected,
    selectedFileIds,
    selectedFolderIds,
    selectableConfig,
    clearSelection,
    selectOnly,
  }
}

export type FilesSelectionController = ReturnType<typeof useFilesSelection>
