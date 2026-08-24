import { beforeEach, describe, expect, it } from 'vitest'
import { useBrowserSessionStore } from '@/stores/browser-session/store'
import { useCopilotTerminalStore } from '@/stores/copilot-terminal/store'
import { useFolderStore } from '@/stores/folders/store'
import { useOperationQueueStore } from '@/stores/operation-queue/store'
import { resetWorkspaceClientState } from './reset-workspace-client-state'

describe('resetWorkspaceClientState', () => {
  beforeEach(() => resetWorkspaceClientState())

  it('clears workspace selection and live desktop scopes', () => {
    useFolderStore.getState().selectOnly('workflow-a')
    useFolderStore.getState().setExpanded('folder-a', true)
    useBrowserSessionStore.getState().activateScope('chat-a')
    useCopilotTerminalStore.getState().activateScope('chat-a')

    resetWorkspaceClientState()

    expect(useFolderStore.getState().selectedWorkflows).toEqual(new Set())
    expect(useFolderStore.getState().expandedFolders).toEqual(new Set())
    expect(useBrowserSessionStore.getState()).toMatchObject({ activeScopeId: null, sessions: {} })
    expect(useCopilotTerminalStore.getState()).toMatchObject({ activeScopeId: null, sessions: {} })
  })

  it('drops collaboration operations and version counters', () => {
    useOperationQueueStore.setState({
      operations: [
        {
          id: 'op-a',
          operation: { operation: 'update', target: 'workflow', payload: {} },
          workflowId: 'workflow-a',
          timestamp: 1,
          retryCount: 0,
          status: 'pending',
          userId: 'user-a',
        },
      ],
      workflowOperationVersions: { 'workflow-a': 2 },
      remoteApplyVersions: { 'workflow-a': 1 },
      isProcessing: true,
      hasOperationError: true,
    })

    resetWorkspaceClientState()

    expect(useOperationQueueStore.getState()).toMatchObject({
      operations: [],
      workflowOperationVersions: {},
      remoteApplyVersions: {},
      isProcessing: false,
      hasOperationError: false,
    })
  })
})
