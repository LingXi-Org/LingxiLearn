'use client'

import { memo } from 'react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Duplicate,
  Eye,
  Link,
  Redo,
  X,
} from '@/components/ui-kit'
import type { ExecutionLogSummaryView } from '@/app/workspace/[workspaceId]/logs/model/execution-log'

interface LogRowContextMenuProps {
  isOpen: boolean
  position: { x: number; y: number }
  onClose: () => void
  log: ExecutionLogSummaryView | null
  onCopyExecutionId: () => void
  onCopyLink: () => void
  onOpenPreview: () => void
  onClearAllFilters: () => void
  onCancelExecution: () => void
  onRetryExecution: () => void
  canCancelExecution: boolean
  isCancelPending?: boolean
  cancelPendingExecutionId?: string
  isRetryPending?: boolean
  hasActiveFilters: boolean
}

/**
 * Context menu for log rows.
 * Provides quick actions for copying data, navigation, and filtering.
 */
export const LogRowContextMenu = memo(function LogRowContextMenu({
  isOpen,
  position,
  onClose,
  log,
  onCopyExecutionId,
  onCopyLink,
  onOpenPreview,
  onClearAllFilters,
  onCancelExecution,
  onRetryExecution,
  canCancelExecution,
  isCancelPending = false,
  cancelPendingExecutionId,
  isRetryPending = false,
  hasActiveFilters,
}: LogRowContextMenuProps) {
  const hasExecutionId = Boolean(log?.identity.executionId)
  const isCancellable = (log?.status === 'running' || log?.status === 'pending') && hasExecutionId
  const isStopping =
    log?.status === 'cancelling' ||
    (isCancelPending && cancelPendingExecutionId === log?.identity.executionId)
  const showCancelAction = canCancelExecution && hasExecutionId && (isCancellable || isStopping)
  const isRetryable = log?.status === 'error' && log.source.kind !== 'unknown'

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
          tabIndex={-1}
          aria-hidden
        />
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align='start'
        side='bottom'
        sideOffset={4}
        onCloseAutoFocus={(e) => e.preventDefault()}
      >
        {isRetryable && (
          <>
            <DropdownMenuItem onSelect={onRetryExecution} disabled={isRetryPending}>
              <Redo />
              {isRetryPending ? '正在重试…' : '重试'}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
          </>
        )}
        {showCancelAction && (
          <>
            <DropdownMenuItem onSelect={onCancelExecution} disabled={isStopping}>
              <X />
              {isStopping ? '正在停止…' : '取消运行'}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
          </>
        )}
        <DropdownMenuItem disabled={!hasExecutionId} onSelect={onCopyExecutionId}>
          <Duplicate />
          复制运行 ID
        </DropdownMenuItem>
        <DropdownMenuItem disabled={!hasExecutionId} onSelect={onCopyLink}>
          <Link />
          复制链接
        </DropdownMenuItem>

        <DropdownMenuSeparator />
        <DropdownMenuItem disabled={!hasExecutionId} onSelect={onOpenPreview}>
          <Eye />
          Open Snapshot
        </DropdownMenuItem>

        <DropdownMenuSeparator />
        {hasActiveFilters && (
          <DropdownMenuItem onSelect={onClearAllFilters}>
            <X />
            Clear Filters
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
})
