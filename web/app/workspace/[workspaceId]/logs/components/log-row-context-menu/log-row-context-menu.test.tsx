/**
 * @vitest-environment jsdom
 */
import { act, type ReactNode } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ExecutionLogSummaryView } from '@/app/workspace/[workspaceId]/logs/model/execution-log'

vi.mock('@/components/ui-kit', () => ({
  DropdownMenu: ({ children, open }: { children: ReactNode; open: boolean }) =>
    open ? <>{children}</> : null,
  DropdownMenuContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  DropdownMenuItem: ({
    children,
    disabled,
    onSelect,
  }: {
    children: ReactNode
    disabled?: boolean
    onSelect?: () => void
  }) => (
    <button type='button' disabled={disabled} onClick={onSelect}>
      {children}
    </button>
  ),
  DropdownMenuSeparator: () => <hr />,
  DropdownMenuTrigger: ({ children }: { children: ReactNode }) => <>{children}</>,
  Duplicate: () => null,
  Eye: () => null,
  Link: () => null,
  Redo: () => null,
  X: () => null,
}))

import { LogRowContextMenu } from './log-row-context-menu'

const LOG: ExecutionLogSummaryView = {
  identity: { logId: 'log-1', executionId: 'execution-1' },
  source: { kind: 'agent-task', title: 'Research task' },
  status: 'running',
  durationMs: null,
  trigger: { type: 'agent-task', label: 'Agent', color: '#ec4899' },
  createdAt: '2026-08-03T00:00:00.000Z',
  costCredits: null,
  costTotalDollars: null,
  pause: { total: 0, resumed: 0, hasPending: false },
}

const callbacks = {
  onClose: vi.fn(),
  onCopyExecutionId: vi.fn(),
  onCopyLink: vi.fn(),
  onOpenPreview: vi.fn(),
  onClearAllFilters: vi.fn(),
  onCancelExecution: vi.fn(),
  onRetryExecution: vi.fn(),
}

let container: HTMLDivElement
let root: Root

beforeEach(() => {
  vi.clearAllMocks()
  container = document.createElement('div')
  document.body.appendChild(container)
  act(() => {
    root = createRoot(container)
  })
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

function renderMenu(
  props: Partial<{
    log: ExecutionLogSummaryView
    canCancelExecution: boolean
    isCancelPending: boolean
    cancelPendingExecutionId: string
  }> = {}
): void {
  act(() => {
    root.render(
      <LogRowContextMenu
        isOpen
        position={{ x: 0, y: 0 }}
        log={props.log ?? LOG}
        canCancelExecution={props.canCancelExecution ?? true}
        isCancelPending={props.isCancelPending}
        cancelPendingExecutionId={props.cancelPendingExecutionId}
        hasActiveFilters={false}
        {...callbacks}
      />
    )
  })
}

function findButton(label: string): HTMLButtonElement | undefined {
  return Array.from(container.querySelectorAll('button')).find(
    (button) => button.textContent?.trim() === label
  )
}

describe('LogRowContextMenu cancellation action', () => {
  it('hides Cancel Run without edit permission', () => {
    renderMenu({ canCancelExecution: false })

    expect(findButton('Cancel Run')).toBeUndefined()
  })

  it('shows an enabled Cancel Run action for an active execution', () => {
    renderMenu()

    expect(findButton('Cancel Run')?.disabled).toBe(false)
  })

  it('shows a disabled Stopping action for a cancelling execution', () => {
    renderMenu({ log: { ...LOG, status: 'cancelling' } })

    expect(findButton('Stopping…')?.disabled).toBe(true)
  })

  it('only disables the execution matching the pending mutation', () => {
    renderMenu({ isCancelPending: true, cancelPendingExecutionId: 'execution-2' })
    expect(findButton('Cancel Run')?.disabled).toBe(false)

    renderMenu({ isCancelPending: true, cancelPendingExecutionId: 'execution-1' })
    expect(findButton('Stopping…')?.disabled).toBe(true)
  })
})
