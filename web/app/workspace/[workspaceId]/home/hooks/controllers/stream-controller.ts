import type { AgentTaskEvent } from '@/lib/lingxi/types'

export interface StreamControllerDependencies {
  subscribeV0: (
    from: number,
    onEvent: (event: AgentTaskEvent) => void,
    onEnd: () => void
  ) => () => void
  subscribeV1: (from: number, onEvent: (event: AgentTaskEvent) => void) => () => void
  catchUpV1: (from: number) => Promise<AgentTaskEvent[]>
  setInterval?: typeof globalThis.setInterval
  clearInterval?: typeof globalThis.clearInterval
}

export interface StreamController {
  startV1(onEvent: (event: AgentTaskEvent) => void): void
  startLegacyV0(from: number, onEvent: (event: AgentTaskEvent) => void, onEnd: () => void): void
  stop(): void
}

/** Owns transport lifetime and the durable V1 cursor; it has no React or router dependency. */
export function createStreamController(
  dependencies: StreamControllerDependencies,
  options: { catchUpIntervalMs?: number } = {}
): StreamController {
  const schedule = dependencies.setInterval ?? globalThis.setInterval
  const unschedule = dependencies.clearInterval ?? globalThis.clearInterval
  const catchUpIntervalMs = options.catchUpIntervalMs ?? 1000
  let stopped = false
  let cursor = 0
  let catchUpInFlight = false
  let mode: 'v1' | 'legacy-v0' | null = null
  let unsubscribeV0: (() => void) | null = null
  let unsubscribeV1: (() => void) | null = null
  let catchUpTimer: ReturnType<typeof globalThis.setInterval> | null = null

  const applyV1 = (event: AgentTaskEvent, onEvent: (event: AgentTaskEvent) => void) => {
    if (stopped) return
    if (typeof event.sequence === 'number') cursor = Math.max(cursor, event.sequence)
    onEvent(event)
  }

  return {
    startV1(onEvent) {
      if (mode && mode !== 'v1') throw new Error('stream_protocol_already_selected')
      mode = 'v1'
      unsubscribeV1?.()
      stopped = false
      // Subscribe before hydration from zero: durable replay plus a monotonic
      // cursor makes opening events impossible to miss and duplicates harmless.
      unsubscribeV1 = dependencies.subscribeV1(0, (event) => applyV1(event, onEvent))
      catchUpTimer = schedule(async () => {
        if (stopped || catchUpInFlight) return
        catchUpInFlight = true
        try {
          const rows = await dependencies.catchUpV1(cursor)
          for (const row of rows.sort((left, right) => left.sequence - right.sequence)) {
            applyV1(row, onEvent)
          }
        } catch {
          // SSE remains primary; polling retries on the next interval.
        } finally {
          catchUpInFlight = false
        }
      }, catchUpIntervalMs)
    },
    startLegacyV0(from, onEvent, onEnd) {
      if (mode && mode !== 'legacy-v0') throw new Error('stream_protocol_already_selected')
      mode = 'legacy-v0'
      unsubscribeV0?.()
      unsubscribeV0 = dependencies.subscribeV0(from, onEvent, onEnd)
    },
    stop() {
      stopped = true
      unsubscribeV0?.()
      unsubscribeV0 = null
      unsubscribeV1?.()
      unsubscribeV1 = null
      if (catchUpTimer !== null) unschedule(catchUpTimer)
      catchUpTimer = null
      mode = null
    },
  }
}
