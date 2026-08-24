/**
 * Lingxi context-chip closure (issue #18 §13).
 *
 * The PromptEditor is shared with Sim; Lingxi only offers the context kinds
 * its backend can actually consume. Anything else (workflow, integration,
 * MCP, browser/terminal tabs, logs) stays hidden rather than rendered as a
 * chip that would silently do nothing.
 */

import type { MothershipResourceType } from '@/lib/copilot/resources/types'
import type { ChatContext } from '@/lib/lingxi/chat-context'

export const LINGXI_CONTEXT_KINDS: ReadonlySet<ChatContext['kind']> = new Set([
  'file',
  'file_selection',
  'table',
  'table_selection',
  'knowledge',
  'past_chat',
  'skill',
])

/**
 * Resource-picker types whose context kind falls outside the closure. These
 * are excluded from the `+` menu and `@`-mention candidates in Lingxi chats.
 */
export const LINGXI_EXCLUDED_RESOURCE_TYPES: ReadonlySet<MothershipResourceType> = new Set([
  'workflow',
  'folder',
  'filefolder',
  'log',
  'integration',
  'generic',
  'browser',
  'terminal',
])

/** Filter an arbitrary context list down to the Lingxi-supported kinds. */
export function filterLingxiContexts(contexts: readonly ChatContext[]): ChatContext[] {
  return contexts.filter((context) => LINGXI_CONTEXT_KINDS.has(context.kind))
}
