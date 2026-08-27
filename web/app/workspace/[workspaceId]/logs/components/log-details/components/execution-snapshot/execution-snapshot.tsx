'use client'

import type React from 'react'
import { useState } from 'react'
import { createPortal } from 'react-dom'
import {
  cn,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  Duplicate,
  Loader,
  Modal,
  ModalBody,
  ModalContent,
  ModalDescription,
  ModalHeader,
} from '@/components/ui-kit'
import { CircleAlert } from '@/components/ui-kit/icons'
import { LingxiRuntimeGraph } from '@/lib/lingxi/components/lingxi-runtime-graph'
import { userFacingError } from '@/lib/product-copy'
import { useExecutionSnapshot } from '@/hooks/queries/logs'

interface ExecutionSnapshotProps {
  executionId: string
  className?: string
  height?: string | number
  width?: string | number
  isModal?: boolean
  isOpen?: boolean
  onClose?: () => void
  live?: boolean
}

export function ExecutionSnapshot({
  executionId,
  className,
  height = '100%',
  width = '100%',
  isModal = false,
  isOpen = false,
  onClose = () => {},
  live = false,
}: ExecutionSnapshotProps) {
  const { data, isLoading, error } = useExecutionSnapshot(executionId, {
    refetchInterval: live ? 1000 : false,
  })

  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const [menuPosition, setMenuPosition] = useState({ x: 0, y: 0 })

  function closeMenu() {
    setIsMenuOpen(false)
  }

  function handleCanvasContextMenu(e: React.MouseEvent) {
    e.preventDefault()
    e.stopPropagation()
    setMenuPosition({ x: e.clientX, y: e.clientY })
    setIsMenuOpen(true)
  }

  function handleCopyExecutionId() {
    navigator.clipboard.writeText(executionId)
    closeMenu()
  }

  const renderContent = () => {
    if (isLoading) {
      return (
        <div
          className={cn('flex items-center justify-center', className)}
          style={{ height, width }}
        >
          <div className='flex items-center gap-2 text-[var(--text-secondary)]'>
            <Loader className='size-[16px]' animate />
            <span className='text-small'>正在加载运行快照…</span>
          </div>
        </div>
      )
    }

    if (error) {
      return (
        <div
          className={cn('flex items-center justify-center', className)}
          style={{ height, width }}
        >
          <div className='flex items-center gap-2 text-[var(--text-error)]'>
            <CircleAlert className='size-[16px]' />
            <span className='text-small'>
              运行快照加载失败：{userFacingError(error, 'loadFailed')}
            </span>
          </div>
        </div>
      )
    }

    if (!data) {
      return (
        <div
          className={cn('flex items-center justify-center', className)}
          style={{ height, width }}
        >
          <div className='flex items-center gap-2 text-[var(--text-secondary)]'>
            <Loader className='size-[16px]' animate />
            <span className='text-small'>正在加载运行快照…</span>
          </div>
        </div>
      )
    }

    return (
      <div
        className={cn('overflow-hidden', className)}
        style={{ height, width }}
        onContextMenu={handleCanvasContextMenu}
        role='application'
        aria-label='Execution canvas'
      >
        <LingxiRuntimeGraph
          key={executionId}
          taskId={data.taskId ?? executionId}
          executionSnapshot={data.snapshot}
          events={[]}
        />
      </div>
    )
  }

  const canvasContextMenu =
    typeof document !== 'undefined'
      ? createPortal(
          <DropdownMenu open={isMenuOpen} onOpenChange={closeMenu} modal={false}>
            <DropdownMenuTrigger asChild>
              <div
                style={{
                  position: 'fixed',
                  left: `${menuPosition.x}px`,
                  top: `${menuPosition.y}px`,
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
              <DropdownMenuItem onSelect={handleCopyExecutionId}>
                <Duplicate />
                Copy Run ID
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>,
          document.body
        )
      : null

  if (isModal) {
    return (
      <>
        <Modal
          open={isOpen}
          onOpenChange={(open) => {
            if (!open) {
              onClose()
            }
          }}
        >
          <ModalContent size='full' className='flex h-[90vh] flex-col'>
            <ModalHeader>执行画布</ModalHeader>

            <ModalBody className='!p-0 min-h-0 flex-1 overflow-hidden'>
              <ModalDescription className='sr-only'>
                View the native execution canvas for this run
              </ModalDescription>
              {renderContent()}
            </ModalBody>
          </ModalContent>
        </Modal>
        {canvasContextMenu}
      </>
    )
  }

  return (
    <>
      {renderContent()}
      {canvasContextMenu}
    </>
  )
}
