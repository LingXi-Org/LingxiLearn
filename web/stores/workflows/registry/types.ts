import type { Edge } from 'reactflow'
import type { BlockState, Loop, Parallel } from '@/lib/workflows/domain/workflow'

export type { WorkflowMetadata } from '@/lib/workflows/domain/metadata'

interface ClipboardData {
  blocks: Record<string, BlockState>
  edges: Edge[]
  subBlockValues: Record<string, Record<string, unknown>>
  loops: Record<string, Loop>
  parallels: Record<string, Parallel>
  timestamp: number
}

export type HydrationPhase = 'idle' | 'creating' | 'state-loading' | 'ready' | 'error'

export interface HydrationState {
  phase: HydrationPhase
  workspaceId: string | null
  workflowId: string | null
  requestId: string | null
  error: string | null
}

interface WorkflowRegistryState {
  activeWorkflowId: string | null
  error: string | null
  hydration: HydrationState
  clipboard: ClipboardData | null
  pendingSelection: string[] | null
}

interface WorkflowRegistryActions {
  setActiveWorkflow: (id: string) => Promise<void>
  loadWorkflowState: (workflowId: string) => Promise<void>
  switchToWorkspace: (id: string) => void
  markWorkflowCreating: (workflowId: string) => void
  markWorkflowCreated: (workflowId: string | null) => void
  copyBlocks: (blockIds: string[]) => void
  preparePasteData: (positionOffset?: { x: number; y: number }) => {
    blocks: Record<string, BlockState>
    edges: Edge[]
    loops: Record<string, Loop>
    parallels: Record<string, Parallel>
    subBlockValues: Record<string, Record<string, unknown>>
  } | null
  hasClipboard: () => boolean
  clearClipboard: () => void
  setPendingSelection: (blockIds: string[]) => void
  clearPendingSelection: () => void
  logout: () => void
}

export type WorkflowRegistry = WorkflowRegistryState & WorkflowRegistryActions
