import { useBrowserSessionStore } from '@/stores/browser-session/store'
import { useCopilotTerminalStore } from '@/stores/copilot-terminal/store'
import { useFolderStore } from '@/stores/folders/store'
import { resetOperationQueue } from '@/stores/operation-queue/store'

/** Clears ephemeral state whose identity is owned by the active workspace. */
export function resetWorkspaceClientState(): void {
  useFolderStore.setState({
    expandedFolders: new Set(),
    selectedWorkflows: new Set(),
    selectedFolders: new Set(),
    lastSelectedFolderId: null,
    selectedChats: new Set(),
    lastSelectedChatId: null,
  })
  useBrowserSessionStore.setState({ activeScopeId: null, sessions: {} })
  useCopilotTerminalStore.setState({
    activeScopeId: null,
    sessions: {},
    settledAgentCommandIds: [],
  })
  resetOperationQueue()
}
