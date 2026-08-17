import { readFileSync } from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

const hookPath = path.resolve(
  process.cwd(),
  'app/workspace/[workspaceId]/home/hooks/use-lingxi-graph-chat.ts'
)
const apiPath = path.resolve(process.cwd(), 'lib/lingxi/api.ts')

describe('Lingxi live V1 stream regressions', () => {
  it('tracks durable row sequence separately from protocol envelope seq', () => {
    const source = readFileSync(hookPath, 'utf-8')
    expect(source).toContain('const v1RowSequenceRef = useRef(0)')
    expect(source).toContain('v1RowSequenceRef.current = Math.max')
    expect(source).not.toContain('from: v1ModelRef.current.lastSeq')
  })

  it('subscribes before history hydration and keeps a cursor catch-up fallback', () => {
    const source = readFileSync(hookPath, 'utf-8')
    const subscribe = source.indexOf('subscribeAgentV1Events(taskId, applyV1Event, { from: 0 })')
    const hydrate = source.indexOf('const loaded = await currentAdapter.loadTask(taskId)')
    expect(subscribe).toBeGreaterThan(-1)
    expect(subscribe).toBeLessThan(hydrate)
    expect(source).toContain('setInterval(() => void catchUpV1(), 1000)')
  })

  it('requests only V1 rows after the durable cursor', () => {
    const source = readFileSync(apiPath, 'utf-8')
    expect(source).toContain('last_event_id=${Math.max(0, from)}')
  })
})
