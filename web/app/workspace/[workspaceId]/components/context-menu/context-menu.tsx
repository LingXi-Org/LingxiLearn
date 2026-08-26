'use client'

import { useRef } from 'react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui-kit'
import {
  Download,
  Duplicate,
  FolderPlus,
  ImageUp,
  Lock,
  LogOut,
  Mail,
  Pencil,
  Pin,
  PinOff,
  Plus,
  SquareArrowUpRight,
  Trash,
  Unlock,
  X,
} from '@/components/ui-kit/icons'

interface ContextMenuProps {
  isOpen: boolean
  position: { x: number; y: number }
  menuRef: React.RefObject<HTMLDivElement | null>
  onClose: () => void
  onOpenInNewTab?: () => void
  openInNewTabLabel?: string
  openInNewTabPosition?: 'first' | 'last'
  separateNavigationAction?: boolean
  groupNonDestructiveActions?: boolean
  onMarkAsRead?: () => void
  onMarkAsUnread?: () => void
  onTogglePin?: () => void
  onRename?: () => void
  /**
   * Ref to the rename input rendered by the "Rename" action, if any. Radix's
   * FocusScope defers its close-time focus teardown to a `setTimeout(0)`, which
   * can run after the rename input's own mount-time `focus()`/`select()` and
   * clobber the selection (the "rename deselects the text" bug). Focusing from
   * `onCloseAutoFocus` runs synchronously inside that same deferred teardown, so
   * it always wins the race regardless of scheduler timing. Only applied when
   * this specific close was caused by selecting "Rename" (see
   * `justSelectedRenameRef`) — an unrelated action closing the menu while an
   * earlier rename is still live must not steal focus back into it.
   */
  renameInputRef?: React.RefObject<HTMLInputElement | null>
  onCreate?: () => void
  onCreateFolder?: () => void
  onDuplicate?: () => void
  onExport?: () => void
  onDelete: () => void
  /**
   * Closes the item rather than deleting it — for tabs, where the destructive
   * action is "close this one", not "delete it forever". Named for the item so
   * it cannot be confused with `onClose`, which dismisses this menu.
   */
  onCloseTab?: () => void
  onCloseOtherTabs?: () => void
  onCloseTabsToRight?: () => void
  showOpenInNewTab?: boolean
  showMarkAsRead?: boolean
  showMarkAsUnread?: boolean
  showPin?: boolean
  isPinned?: boolean
  showRename?: boolean
  showCreate?: boolean
  showCreateFolder?: boolean
  showDuplicate?: boolean
  showExport?: boolean
  disableExport?: boolean
  disableMarkAsRead?: boolean
  disableMarkAsUnread?: boolean
  disableRename?: boolean
  disableDuplicate?: boolean
  disableDelete?: boolean
  disableCreate?: boolean
  disableCreateFolder?: boolean
  onLeave?: () => void
  showLeave?: boolean
  disableLeave?: boolean
  onToggleLock?: () => void
  showLock?: boolean
  disableLock?: boolean
  isLocked?: boolean
  showDelete?: boolean
  showCloseTab?: boolean
  disableCloseOtherTabs?: boolean
  disableCloseTabsToRight?: boolean
  onUploadLogo?: () => void
  showUploadLogo?: boolean
  disableUploadLogo?: boolean
}

/**
 * Context menu component for workflow, folder, and workspace items.
 * Uses DropdownMenu for accessible, hover-expandable submenus.
 */
export function ContextMenu({
  isOpen,
  position,
  menuRef,
  onClose,
  onOpenInNewTab,
  openInNewTabLabel = 'Open in new tab',
  openInNewTabPosition = 'first',
  separateNavigationAction = false,
  groupNonDestructiveActions = false,
  onMarkAsRead,
  onMarkAsUnread,
  onTogglePin,
  onRename,
  renameInputRef,
  onCreate,
  onCreateFolder,
  onDuplicate,
  onExport,
  onDelete,
  onCloseTab,
  onCloseOtherTabs,
  onCloseTabsToRight,
  showOpenInNewTab = false,
  showMarkAsRead = false,
  showMarkAsUnread = false,
  showPin = false,
  isPinned = false,
  showRename = true,
  showCreate = false,
  showCreateFolder = false,
  showDuplicate = true,
  showExport = false,
  disableExport = false,
  disableMarkAsRead = false,
  disableMarkAsUnread = false,
  disableRename = false,
  disableDuplicate = false,
  disableDelete = false,
  disableCreate = false,
  disableCreateFolder = false,
  onLeave,
  showLeave = false,
  disableLeave = false,
  onToggleLock,
  showLock = false,
  disableLock = false,
  isLocked = false,
  showDelete = true,
  showCloseTab = false,
  disableCloseOtherTabs = false,
  disableCloseTabsToRight = false,
  onUploadLogo,
  showUploadLogo = false,
  disableUploadLogo = false,
}: ContextMenuProps) {
  const hasNavigationSection = showOpenInNewTab && onOpenInNewTab
  const hasStatusSection =
    (showMarkAsRead && onMarkAsRead) ||
    (showMarkAsUnread && onMarkAsUnread) ||
    (showPin && onTogglePin)
  const hasEditSection =
    (showRename && onRename) ||
    (showCreate && onCreate) ||
    (showCreateFolder && onCreateFolder) ||
    (showLock && onToggleLock) ||
    (showUploadLogo && onUploadLogo)
  const hasCopySection = (showDuplicate && onDuplicate) || (showExport && onExport)

  /**
   * Only the "Rename" item should trigger the `onCloseAutoFocus` refocus below —
   * an unrelated action (Delete, Duplicate, ...) closing this menu while a rename
   * from an earlier interaction is still live must not steal focus back into it.
   */
  const justSelectedRenameRef = useRef(false)

  return (
    <DropdownMenu open={isOpen} onOpenChange={(open) => !open && onClose()} modal={false}>
      <DropdownMenuTrigger asChild>
        <div
          style={{
            position: 'fixed',
            left: `${position.x}px`,
            top: `${position.y}px`,
            width: '1px',
            height: '1px',
            pointerEvents: 'none',
          }}
        />
      </DropdownMenuTrigger>
      <DropdownMenuContent
        ref={menuRef}
        align='start'
        side='bottom'
        sideOffset={4}
        className='max-h-[var(--radix-dropdown-menu-content-available-height,400px)]'
        onCloseAutoFocus={(e) => {
          e.preventDefault()
          const shouldFocusRenameInput = justSelectedRenameRef.current
          justSelectedRenameRef.current = false
          const input = shouldFocusRenameInput ? renameInputRef?.current : null
          if (input) {
            input.focus()
            input.select()
          }
        }}
      >
        {hasNavigationSection && openInNewTabPosition === 'first' && separateNavigationAction && (
          <>
            <DropdownMenuItem onSelect={onOpenInNewTab}>
              <SquareArrowUpRight />
              {openInNewTabLabel}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
          </>
        )}

        {hasStatusSection && (
          <>
            {showMarkAsRead && onMarkAsRead && (
              <DropdownMenuItem disabled={disableMarkAsRead} onSelect={onMarkAsRead}>
                <Mail />
                Mark as read
              </DropdownMenuItem>
            )}
            {showMarkAsUnread && onMarkAsUnread && (
              <DropdownMenuItem disabled={disableMarkAsUnread} onSelect={onMarkAsUnread}>
                <Mail />
                Mark as unread
              </DropdownMenuItem>
            )}
            {showPin && onTogglePin && (
              <DropdownMenuItem onSelect={onTogglePin}>
                {isPinned ? <PinOff /> : <Pin />}
                {isPinned ? 'Unpin' : 'Pin'}
              </DropdownMenuItem>
            )}
            <DropdownMenuSeparator />
          </>
        )}

        {hasEditSection && (
          <>
            {showRename && onRename && (
              <DropdownMenuItem
                disabled={disableRename}
                onSelect={() => {
                  justSelectedRenameRef.current = true
                  onRename()
                }}
              >
                <Pencil />
                Rename
              </DropdownMenuItem>
            )}
            {showCreate && onCreate && (
              <DropdownMenuItem disabled={disableCreate} onSelect={onCreate}>
                <Plus />
                Create
              </DropdownMenuItem>
            )}
            {showCreateFolder && onCreateFolder && (
              <DropdownMenuItem disabled={disableCreateFolder} onSelect={onCreateFolder}>
                <FolderPlus />
                Create folder
              </DropdownMenuItem>
            )}
            {showLock && onToggleLock && (
              <DropdownMenuItem disabled={disableLock} onSelect={onToggleLock}>
                {isLocked ? <Unlock /> : <Lock />}
                {isLocked ? 'Unlock' : 'Lock'}
              </DropdownMenuItem>
            )}
            {showUploadLogo && onUploadLogo && (
              <DropdownMenuItem disabled={disableUploadLogo} onSelect={onUploadLogo}>
                <ImageUp />
                Upload logo
              </DropdownMenuItem>
            )}
            <DropdownMenuSeparator />
          </>
        )}

        {hasCopySection && (
          <>
            {showDuplicate && onDuplicate && (
              <DropdownMenuItem disabled={disableDuplicate} onSelect={onDuplicate}>
                <Duplicate />
                Duplicate
              </DropdownMenuItem>
            )}
            {showExport && onExport && (
              <DropdownMenuItem disabled={disableExport} onSelect={onExport}>
                <Download />
                Export
              </DropdownMenuItem>
            )}
            <DropdownMenuSeparator />
          </>
        )}

        {showOpenInNewTab &&
          onOpenInNewTab &&
          (!separateNavigationAction || openInNewTabPosition === 'last') && (
            <DropdownMenuItem onSelect={onOpenInNewTab}>
              <SquareArrowUpRight />
              {openInNewTabLabel}
            </DropdownMenuItem>
          )}

        {showLeave && onLeave && (
          <DropdownMenuItem disabled={disableLeave} onSelect={onLeave}>
            <LogOut />
            Leave
          </DropdownMenuItem>
        )}

        {showCloseTab && onCloseTab && (
          <>
            <DropdownMenuItem onSelect={onCloseTab}>
              <X />
              Close tab
            </DropdownMenuItem>
            {onCloseOtherTabs && (
              <DropdownMenuItem disabled={disableCloseOtherTabs} onSelect={onCloseOtherTabs}>
                <X />
                Close other tabs
              </DropdownMenuItem>
            )}
            {onCloseTabsToRight && (
              <DropdownMenuItem disabled={disableCloseTabsToRight} onSelect={onCloseTabsToRight}>
                <X />
                Close tabs to right
              </DropdownMenuItem>
            )}
          </>
        )}

        {showDelete && onDelete && (
          <DropdownMenuItem disabled={disableDelete} onSelect={onDelete}>
            <Trash />
            Delete
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
