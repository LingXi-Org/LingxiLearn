'use client'

import { type DragEvent, useCallback, useMemo, useRef, useState } from 'react'
import { createLogger } from '@/lib/logger'
import type { RowDragDropConfig } from '@/app/workspace/[workspaceId]/components'
import { parseFilesRowId } from '@/app/workspace/[workspaceId]/files/lib/file-row-ids'

const logger = createLogger('Files')

/**
 * Private drag payload, namespaced so a drag started on another surface (or an external
 * drag) is never mistaken for a Files row. Kept stable across the split — drops can begin
 * in one mount of this page and land in another.
 */
const DRAG_ROW_MIME = 'application/x-sim-workspace-file-rows'

const DRAG_GHOST_STYLE =
  'position:fixed;top:-500px;left:0;display:inline-flex;align-items:center;padding:4px 10px;background:var(--surface-active);border:1px solid var(--border);border-radius:8px;font-family:system-ui,-apple-system,sans-serif;font-size:13px;color:var(--text-body);white-space:nowrap;pointer-events:none;box-shadow:var(--shadow-medium);z-index:var(--z-toast)'

const hasExternalFiles = (dataTransfer: DataTransfer): boolean =>
  dataTransfer.types.includes('Files')

export interface UseFilesRowDragDropParams {
  /** From the command matrix — drag and drop are moves, i.e. edits. */
  canMove: boolean
  /** Row currently being renamed inline, which must stay editable rather than draggable. */
  editingRowId: string | null
  selectedRowIds: ReadonlySet<string>
  visibleRowIds: string[]
  /** Transitive descendants of each folder, from the shared `buildDescendantIndex`. */
  descendantIndex: Map<string, Set<string>>
  /** Current `folderId` of a file row, for rejecting a no-op drop. */
  getFileFolderId: (fileId: string) => string | null | undefined
  /** Current `parentId` of a folder row, for rejecting a no-op drop. */
  getFolderParentId: (folderId: string) => string | null | undefined
  /** Display name for the drag ghost. */
  getRowLabel: (rowId: string) => string | undefined
  /** Dragging an unselected row selects it first, so the drop moves what the ghost shows. */
  onDragSelect: (rowId: string, index: number) => void
  /** Moves rows into a folder; resolves after the mutation settles. */
  onMoveItems: (fileIds: string[], folderIds: string[], targetFolderId: string) => Promise<void>
  /** External OS files dropped onto a folder row upload straight into it. */
  uploadFiles: (files: File[], targetFolderId: string) => void | Promise<void>
  /** Clears the page-level drop overlay, owned by the upload controller. */
  resetExternalDrag: () => void
}

/**
 * Drag-a-row-onto-a-folder-row moves for the Files list. Unlike the shared single-row
 * `useFolderRowDragDrop`, this drags multi-selections (a selected row drags the whole
 * selection) and accepts external OS file drops on folder rows.
 */
export function useFilesRowDragDrop({
  canMove,
  editingRowId,
  selectedRowIds,
  visibleRowIds,
  descendantIndex,
  getFileFolderId,
  getFolderParentId,
  getRowLabel,
  onDragSelect,
  onMoveItems,
  uploadFiles,
  resetExternalDrag,
}: UseFilesRowDragDropParams): RowDragDropConfig {
  const [activeDropTargetId, setActiveDropTargetId] = useState<string | null>(null)
  const [draggedRowIds, setDraggedRowIds] = useState<Set<string>>(() => new Set())

  /**
   * In-flight drag sources, mirrored outside React state because `onDragOver` fires far
   * faster than a re-render and must decide drop validity synchronously.
   */
  const draggedRowIdsRef = useRef<string[]>([])
  const dragGhostRef = useRef<HTMLElement | null>(null)

  const optionsRef = useRef({
    descendantIndex,
    getFileFolderId,
    getFolderParentId,
    getRowLabel,
    onMoveItems,
    uploadFiles,
    resetExternalDrag,
  })
  optionsRef.current = {
    descendantIndex,
    getFileFolderId,
    getFolderParentId,
    getRowLabel,
    onMoveItems,
    uploadFiles,
    resetExternalDrag,
  }

  const isInvalidDropTarget = useCallback((targetRowId: string, sourceRowIds: string[]) => {
    const target = parseFilesRowId(targetRowId)
    if (target.kind !== 'folder') return true

    for (const sourceRowId of sourceRowIds) {
      const source = parseFilesRowId(sourceRowId)
      if (source.kind !== 'folder') continue
      if (source.id === target.id) return true
      if (optionsRef.current.descendantIndex.get(source.id)?.has(target.id)) return true
    }

    // Reject drop if every dragged item is already a direct child of the target
    const allAlreadyInTarget = sourceRowIds.every((sourceRowId) => {
      const source = parseFilesRowId(sourceRowId)
      if (source.kind === 'file') {
        return optionsRef.current.getFileFolderId(source.id) === target.id
      }
      return (optionsRef.current.getFolderParentId(source.id) ?? null) === target.id
    })
    if (allAlreadyInTarget) return true

    return false
  }, [])

  return useMemo<RowDragDropConfig>(
    () => ({
      activeDropTargetId,
      draggedRowIds,
      isAnyDragActive: draggedRowIds.size > 0,
      isRowDraggable: (rowId) => canMove && editingRowId !== rowId,
      isRowDropTarget: (rowId) => canMove && parseFilesRowId(rowId).kind === 'folder',
      onDragStart: (e: DragEvent<HTMLDivElement>, rowId) => {
        if (!canMove || editingRowId === rowId) {
          e.preventDefault()
          return
        }

        const sourceRowIds = selectedRowIds.has(rowId)
          ? visibleRowIds.filter((visibleRowId) => selectedRowIds.has(visibleRowId))
          : [rowId]

        draggedRowIdsRef.current = sourceRowIds
        setDraggedRowIds(new Set(sourceRowIds))
        if (!selectedRowIds.has(rowId)) {
          onDragSelect(rowId, visibleRowIds.indexOf(rowId))
        }

        e.dataTransfer.effectAllowed = 'move'
        e.dataTransfer.setData(DRAG_ROW_MIME, JSON.stringify(sourceRowIds))
        e.dataTransfer.setData('text/plain', sourceRowIds.join(','))

        const count = sourceRowIds.length
        const firstName = optionsRef.current.getRowLabel(sourceRowIds[0])
        const ghostLabel =
          count > 1 ? `${firstName ?? 'Items'} +${count - 1} more` : (firstName ?? 'Item')
        const ghost = document.createElement('div')
        ghost.style.cssText = DRAG_GHOST_STYLE
        const text = document.createElement('span')
        text.style.cssText = 'max-width:200px;overflow:hidden;text-overflow:ellipsis'
        text.textContent = ghostLabel
        ghost.appendChild(text)
        document.body.appendChild(ghost)
        // Force a layout pass so the drag image is measurable before it is captured.
        void ghost.offsetHeight
        e.dataTransfer.setDragImage(ghost, ghost.offsetWidth / 2, ghost.offsetHeight / 2)
        dragGhostRef.current = ghost
      },
      onDragOver: (e: DragEvent<HTMLDivElement>, rowId) => {
        const sourceRowIds = draggedRowIdsRef.current
        const isExternalFileDrag = hasExternalFiles(e.dataTransfer)
        if (!isExternalFileDrag && isInvalidDropTarget(rowId, sourceRowIds)) return

        e.preventDefault()
        e.stopPropagation()
        e.dataTransfer.dropEffect = isExternalFileDrag ? 'copy' : 'move'
        setActiveDropTargetId(rowId)
      },
      onDragLeave: (e: DragEvent<HTMLDivElement>, rowId) => {
        const relatedTarget = e.relatedTarget
        if (relatedTarget instanceof Node && e.currentTarget.contains(relatedTarget)) return
        setActiveDropTargetId((current) => (current === rowId ? null : current))
      },
      onDrop: (e: DragEvent<HTMLDivElement>, rowId) => {
        e.preventDefault()
        e.stopPropagation()
        optionsRef.current.resetExternalDrag()
        setActiveDropTargetId(null)
        const target = parseFilesRowId(rowId)
        if (target.kind !== 'folder') return

        const droppedFiles = Array.from(e.dataTransfer.files ?? [])
        if (droppedFiles.length > 0) {
          void optionsRef.current.uploadFiles(droppedFiles, target.id)
          return
        }

        let sourceRowIds = draggedRowIdsRef.current
        const rawSource = e.dataTransfer.getData(DRAG_ROW_MIME)
        if (rawSource) {
          try {
            const parsedSource = JSON.parse(rawSource)
            if (Array.isArray(parsedSource)) {
              sourceRowIds = parsedSource.filter(
                (source): source is string => typeof source === 'string' && source.length > 0
              )
            }
          } catch {
            sourceRowIds = draggedRowIdsRef.current
          }
        }

        if (isInvalidDropTarget(rowId, sourceRowIds)) return

        const fileIds = sourceRowIds
          .map(parseFilesRowId)
          .filter((source) => source.kind === 'file')
          .map((source) => source.id)
        const folderIds = sourceRowIds
          .map(parseFilesRowId)
          .filter((source) => source.kind === 'folder')
          .map((source) => source.id)

        if (fileIds.length === 0 && folderIds.length === 0) return

        optionsRef.current.onMoveItems(fileIds, folderIds, target.id).catch((error) => {
          logger.error('Failed to move items via drag and drop:', error)
        })
      },
      onDragEnd: () => {
        if (dragGhostRef.current) {
          dragGhostRef.current.remove()
          dragGhostRef.current = null
        }
        draggedRowIdsRef.current = []
        setDraggedRowIds(new Set())
        optionsRef.current.resetExternalDrag()
        setActiveDropTargetId(null)
      },
    }),
    [
      activeDropTargetId,
      draggedRowIds,
      canMove,
      editingRowId,
      selectedRowIds,
      visibleRowIds,
      onDragSelect,
      isInvalidDropTarget,
    ]
  )
}
