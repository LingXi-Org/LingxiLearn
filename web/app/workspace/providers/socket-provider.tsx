'use client'

import { createContext, type ReactNode, useContext } from 'react'

/**
 * Sim's Socket.IO workflow collaboration boundary is retained for component
 * compatibility, but LingxiGraph uses HTTP/SSE task events instead. No socket
 * client is created and no workflow room is joined in the static frontend.
 */
export interface SocketContextType {
  socket: null
  isConnected: false
  isConnecting: false
  isReconnecting: false
  isRetryingWorkflowJoin: false
  authFailed: false
  blockedJoinWorkflowId: null
  currentWorkflowId: null
  currentSocketId: null
  joinWorkflow: (workflowId: string) => void
  leaveWorkflow: () => void
  retryConnection: () => void
  emitWorkflowOperation: (...args: never[]) => false
  emitSubblockUpdate: (...args: never[]) => false
  emitVariableUpdate: (...args: never[]) => false
  emitCursorUpdate: (...args: never[]) => void
  emitSelectionUpdate: (...args: never[]) => void
  onWorkflowOperation: (...args: never[]) => void
  onSubblockUpdate: (...args: never[]) => void
  onVariableUpdate: (...args: never[]) => void
  onCursorUpdate: (...args: never[]) => void
  onSelectionUpdate: (...args: never[]) => void
  onWorkflowDeleted: (...args: never[]) => void
  onAccessRevoked: (...args: never[]) => void
  onWorkflowReverted: (...args: never[]) => void
  onWorkflowUpdated: (...args: never[]) => void
  onWorkflowDeployed: (...args: never[]) => void
  onOperationConfirmed: (...args: never[]) => void
  onOperationFailed: (...args: never[]) => void
}

const SOCKET_CONTEXT: SocketContextType = {
  socket: null,
  isConnected: false,
  isConnecting: false,
  isReconnecting: false,
  isRetryingWorkflowJoin: false,
  authFailed: false,
  blockedJoinWorkflowId: null,
  currentWorkflowId: null,
  currentSocketId: null,
  joinWorkflow: () => {},
  leaveWorkflow: () => {},
  retryConnection: () => {},
  emitWorkflowOperation: () => false,
  emitSubblockUpdate: () => false,
  emitVariableUpdate: () => false,
  emitCursorUpdate: () => {},
  emitSelectionUpdate: () => {},
  onWorkflowOperation: () => {},
  onSubblockUpdate: () => {},
  onVariableUpdate: () => {},
  onCursorUpdate: () => {},
  onSelectionUpdate: () => {},
  onWorkflowDeleted: () => {},
  onAccessRevoked: () => {},
  onWorkflowReverted: () => {},
  onWorkflowUpdated: () => {},
  onWorkflowDeployed: () => {},
  onOperationConfirmed: () => {},
  onOperationFailed: () => {},
}

const SocketContext = createContext<SocketContextType>(SOCKET_CONTEXT)

export function useSocket() {
  return useContext(SocketContext)
}

export function SocketProvider({ children }: { children: ReactNode; user?: unknown }) {
  return <SocketContext.Provider value={SOCKET_CONTEXT}>{children}</SocketContext.Provider>
}
