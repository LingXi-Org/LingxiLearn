'use client'

import { createContext, type ReactNode, useContext } from 'react'

/**
 * Sim's Socket.IO workflow collaboration boundary is retained for component
 * compatibility, but LingxiGraph uses HTTP/SSE task events instead. No socket
 * client is created and no workflow room is joined in the static frontend.
 */
export interface LingxiSocketCompat {
  id?: string
  connected: boolean
  on: (...args: any[]) => void
  off: (...args: any[]) => void
  emit: (...args: any[]) => void
}

export interface SocketContextType {
  socket: LingxiSocketCompat | null
  isConnected: boolean
  isConnecting: boolean
  isReconnecting: boolean
  isRetryingWorkflowJoin: boolean
  authFailed: false
  blockedJoinWorkflowId: null
  currentWorkflowId: null
  currentSocketId: null
  joinWorkflow: (workflowId: string) => void
  leaveWorkflow: () => void
  retryConnection: () => void
  emitWorkflowOperation: (...args: any[]) => boolean
  emitSubblockUpdate: (...args: any[]) => boolean
  emitVariableUpdate: (...args: any[]) => boolean
  emitCursorUpdate: (...args: any[]) => void
  emitSelectionUpdate: (...args: any[]) => void
  onWorkflowOperation: (...args: any[]) => void
  onSubblockUpdate: (...args: any[]) => void
  onVariableUpdate: (...args: any[]) => void
  onCursorUpdate: (...args: any[]) => void
  onSelectionUpdate: (...args: any[]) => void
  onWorkflowDeleted: (...args: any[]) => void
  onAccessRevoked: (...args: any[]) => void
  onWorkflowReverted: (...args: any[]) => void
  onWorkflowUpdated: (...args: any[]) => void
  onWorkflowDeployed: (...args: any[]) => void
  onOperationConfirmed: (...args: any[]) => void
  onOperationFailed: (...args: any[]) => void
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
