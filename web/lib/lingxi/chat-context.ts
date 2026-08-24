export interface BrowserTextSelection {
  text: string
  url?: string
  title?: string
}

export interface TerminalTextSelection {
  text: string
  startLine: number
  endLine: number
}

/** Stable context vocabulary exchanged by workspace chat surfaces. */
export type ChatContext =
  | { kind: 'past_chat'; chatId: string; label: string }
  | { kind: 'workflow'; workflowId: string; label: string }
  | { kind: 'current_workflow'; workflowId: string; label: string }
  | { kind: 'blocks'; blockIds: string[]; label: string }
  | { kind: 'logs'; executionId?: string; label: string }
  | { kind: 'workflow_block'; workflowId: string; blockId: string; label: string }
  | { kind: 'knowledge'; knowledgeId?: string; label: string }
  | { kind: 'table'; tableId: string; label: string }
  | {
      kind: 'table_selection'
      tableId: string
      label: string
      tableName: string
      rowIds: string[]
      columnIds?: string[]
    }
  | { kind: 'file'; fileId: string; label: string }
  | {
      kind: 'file_selection'
      fileId: string
      label: string
      fileName: string
      text: string
      startLine?: number
      endLine?: number
    }
  | { kind: 'folder'; folderId: string; label: string }
  | { kind: 'filefolder'; fileFolderId: string; label: string }
  | { kind: 'docs'; label: string }
  | { kind: 'browser_tab'; tabId: string; label: string; selection?: BrowserTextSelection }
  | { kind: 'terminal_tab'; terminalId: string; label: string; selection?: TerminalTextSelection }
  | { kind: 'slash_command'; command: string; label: string }
  | { kind: 'integration'; blockType: string; label: string }
  | { kind: 'skill'; skillId: string; label: string }
  | { kind: 'mcp'; serverId: string; label: string }
