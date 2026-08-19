import { readFileSync } from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

const hookPath = path.resolve(
  process.cwd(),
  'app/workspace/[workspaceId]/home/hooks/use-lingxi-graph-chat.ts'
)
const apiPath = path.resolve(process.cwd(), 'lib/api/domains/agent-tasks.ts')
const streamControllerPath = path.resolve(
  process.cwd(),
  'app/workspace/[workspaceId]/home/hooks/controllers/stream-controller.ts'
)

describe('Lingxi live V1 stream regressions', () => {
  it('tracks durable row sequence separately from protocol envelope seq', () => {
    const source = readFileSync(hookPath, 'utf-8')
    expect(source).toContain('const v1RowSequenceRef = useRef(0)')
    expect(source).toContain('v1RowSequenceRef.current = Math.max')
    expect(source).not.toContain('from: v1ModelRef.current.lastSeq')
  })

  it('subscribes before history hydration and keeps a cursor catch-up fallback', () => {
    const source = readFileSync(hookPath, 'utf-8')
    const subscribe = source.indexOf('stream.startV1(applyV1Event)')
    const hydrate = source.indexOf('const loaded = await currentAdapter.loadTask(taskId)')
    expect(subscribe).toBeGreaterThan(-1)
    expect(subscribe).toBeLessThan(hydrate)
    const controller = readFileSync(streamControllerPath, 'utf-8')
    expect(controller).toContain('dependencies.subscribeV1(0')
    expect(controller).toContain('dependencies.catchUpV1(cursor)')
    expect(controller).toContain('catchUpIntervalMs ?? 1000')
  })

  it('requests only V1 rows after the durable cursor', () => {
    const source = readFileSync(apiPath, 'utf-8')
    expect(source).toContain('last_event_id=${Math.max(0, from)}')
  })
})


describe('Lingxi runtime graph live refresh regression', () => {
  it('refreshes the graph from V0 lifecycle events and V1 replay/catch-up events', () => {
    const source = readFileSync(hookPath, 'utf-8')
    expect(source).toContain('RUNTIME_GRAPH_REFRESH_EVENTS.has(event.kind)')
    expect(source).toContain("envelope.type === 'run' || envelope.type === 'span'")
    expect(source).toContain('scheduleRuntimeGraphRefresh()')
    expect(source).toContain('api.runtimeGraph(taskId)')
  })
})
