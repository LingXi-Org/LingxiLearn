import type { AgentTaskEvent, SimExecutionSnapshot } from './types'

/** Frontend transport adapter: the server projection is authoritative. */
export interface SimRuntimeState {
  executionId: string | null
  workflowState: Record<string, any> | null
  traceSpans: Array<Record<string, any>>
  events: AgentTaskEvent[]
}

export function createSimRuntimeState(snapshot?: SimExecutionSnapshot | null): SimRuntimeState {
  return {
    executionId: snapshot?.executionId ?? null,
    workflowState: snapshot?.workflowState ?? null,
    traceSpans: snapshot?.traceSpans ?? [],
    events: [],
  }
}

/** Apply persisted SSE events without inventing a client-side execution graph. */
export function applySimRuntimeEvent(
  state: SimRuntimeState,
  event: AgentTaskEvent
): SimRuntimeState {
  const runtime = event.runtime ?? (event.payload.runtime as Record<string, unknown> | undefined)
  const executionId =
    event.execution_id ?? (runtime?.execution_id as string | undefined) ?? state.executionId
  const workflowPatch =
    event.workflowState ?? (event.payload.workflowState as Record<string, unknown> | undefined)
  const traceSpans = event.payload.traceSpans as Array<Record<string, unknown>> | undefined
  return {
    executionId: executionId ?? null,
    workflowState: workflowPatch
      ? { ...(state.workflowState ?? {}), ...workflowPatch }
      : state.workflowState,
    traceSpans: traceSpans ?? state.traceSpans,
    events: state.events.some((item) => item.sequence === event.sequence)
      ? state.events
      : [...state.events, event].sort((a, b) => a.sequence - b.sequence),
  }
}

export function replaySimRuntimeEvents(
  snapshot: SimExecutionSnapshot | null | undefined,
  events: AgentTaskEvent[]
): SimRuntimeState {
  return events.reduce(applySimRuntimeEvent, createSimRuntimeState(snapshot))
}
