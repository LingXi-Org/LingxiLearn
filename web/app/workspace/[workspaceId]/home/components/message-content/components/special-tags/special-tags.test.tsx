/**
 * @vitest-environment jsdom
 */
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const {
  mockFinishTerminalHandoff,
  mockIsBrowserAgentAvailable,
  mockIsTerminalAvailable,
  mockSendBrowserPanelAction,
} = vi.hoisted(() => ({
  mockFinishTerminalHandoff: vi.fn(),
  mockIsBrowserAgentAvailable: vi.fn(() => false),
  mockIsTerminalAvailable: vi.fn(() => false),
  mockSendBrowserPanelAction: vi.fn(),
}))

vi.mock('next/navigation', () => ({
  useParams: () => ({ workspaceId: 'lingxi' }),
}))

vi.mock('@/app/workspace/[workspaceId]/home/components/chat-surface-context', () => ({
  useChatSurface: () => ({ chatId: 'chat-1' }),
}))

vi.mock('@/lib/browser-agent/transport', () => ({
  isBrowserAgentAvailable: mockIsBrowserAgentAvailable,
  sendBrowserPanelAction: mockSendBrowserPanelAction,
}))

vi.mock('@/lib/terminal/transport', () => ({
  finishTerminalHandoff: mockFinishTerminalHandoff,
  isTerminalAvailable: mockIsTerminalAvailable,
}))

import type { CredentialItemData } from '@/app/workspace/[workspaceId]/home/components/message-content/components/special-tags/special-tags'
import { SpecialTags } from '@/app/workspace/[workspaceId]/home/components/message-content/components/special-tags/special-tags'

function renderCredential(data: CredentialItemData): { container: HTMLDivElement; root: Root } {
  ;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  const container = document.createElement('div')
  const root = createRoot(container)
  act(() => {
    root.render(<SpecialTags segment={{ type: 'credential', data: [data] }} />)
  })
  return { container, root }
}

describe('native credential handoffs', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockIsBrowserAgentAvailable.mockReturnValue(false)
    mockIsTerminalAvailable.mockReturnValue(false)
  })

  it('returns browser takeover completion through the native panel transport', () => {
    mockIsBrowserAgentAvailable.mockReturnValue(true)
    const { container, root } = renderCredential({
      type: 'browser_takeover',
      name: 'Complete the verification in the browser.',
    })

    expect(container.textContent).toContain('Complete the verification in the browser.')
    const continueButton = Array.from(container.querySelectorAll('button')).find(
      (button) => button.textContent === 'Continue'
    )
    act(() => continueButton?.click())

    expect(mockSendBrowserPanelAction).toHaveBeenCalledWith(
      'takeover-done',
      {},
      'chat-1'
    )
    act(() => root.unmount())
  })

  it('does not expose a browser control when the native bridge is unavailable', () => {
    const { container, root } = renderCredential({ type: 'browser_takeover', name: 'Continue' })
    expect(container.textContent).toBe('')
    act(() => root.unmount())
  })

  it('hands terminal control back once through the native terminal transport', () => {
    mockIsTerminalAvailable.mockReturnValue(true)
    const { container, root } = renderCredential({
      type: 'terminal_handoff',
      name: 'Finish the interactive prompt.',
      value: 'terminal-7',
    })

    const button = container.querySelector('button')
    expect(button?.textContent).toContain('Finish the interactive prompt.')
    act(() => button?.click())

    expect(mockFinishTerminalHandoff).toHaveBeenCalledWith('terminal-7', 'chat-1')
    expect(button?.textContent).toContain('已将控制权交还给灵犀')
    act(() => button?.click())
    expect(mockFinishTerminalHandoff).toHaveBeenCalledTimes(1)
    act(() => root.unmount())
  })
})
