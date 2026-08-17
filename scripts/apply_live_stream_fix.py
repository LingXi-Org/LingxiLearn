from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_routes() -> None:
    path = Path("server/lingxilearn/api/routes.py")
    replace_once(
        path,
        '''    # V1 clients (protocol=v1) read the versioned Mothership stream; everyone
    # else keeps the historical V0 event vocabulary, unchanged.
    protocol_version = 1 if request.query_params.get("protocol") == "v1" else 0

    # History hydration uses one atomic JSON snapshot so the client can render
    # the final graph state without replaying every old event as a new run.
    if request.query_params.get("format") == "json":
        events = await svc.repo.agent_events_after_for_learner(
            task_id,
            context.learner_id,
            0,
            protocol_version=protocol_version,
        )
        return Response(
            content=json.dumps({"events": events}, ensure_ascii=False, separators=(",", ":")),
            media_type="application/json",
        )

    header = request.headers.get("last-event-id") or request.query_params.get("last_event_id")
    try:
        cursor = int(header) if header else 0
    except ValueError:
        cursor = 0
''',
        '''    # V1 clients (protocol=v1) read the versioned Mothership stream; everyone
    # else keeps the historical V0 event vocabulary, unchanged.
    protocol_version = 1 if request.query_params.get("protocol") == "v1" else 0

    # Both SSE replay and JSON catch-up use the durable AgentTaskEvent row
    # sequence.  This is intentionally different from the protocol envelope's
    # own `seq`, because V0 and V1 rows share one database event log.
    header = request.headers.get("last-event-id") or request.query_params.get("last_event_id")
    try:
        cursor = int(header) if header else 0
    except ValueError:
        cursor = 0

    # History hydration is also the fallback catch-up transport for clients
    # behind proxies that buffer a long-lived SSE response.  Respect the same
    # cursor so polling transfers only rows the client has not consumed.
    if request.query_params.get("format") == "json":
        events = await svc.repo.agent_events_after_for_learner(
            task_id,
            context.learner_id,
            cursor,
            protocol_version=protocol_version,
        )
        return Response(
            content=json.dumps({"events": events}, ensure_ascii=False, separators=(",", ":")),
            media_type="application/json",
        )
''',
    )


def patch_db() -> None:
    path = Path("server/lingxilearn/store/db.py")
    replace_once(
        path,
        '''            if row is None:
                row = FactSnapshot(
                    id=f"facts_{uuid4().hex}",
                    task_id=task_id,
                    turn_id=turn_id,
                    plan_revision=plan_revision,
                    facts=dict(facts),
                    evidence_refs=list(evidence_refs or []),
                    artifact_refs=list(artifact_refs or []),
                )
                s.add(row)
                await s.commit()
            return {
                "id": row.id,
                "facts": dict(row.facts),
                "evidence_refs": list(row.evidence_refs),
                "artifact_refs": list(row.artifact_refs),
            }
''',
        '''            if row is None:
                row = FactSnapshot(
                    id=f"facts_{uuid4().hex}",
                    task_id=task_id,
                    turn_id=turn_id,
                    plan_revision=plan_revision,
                    facts=dict(facts),
                    evidence_refs=list(evidence_refs or []),
                    artifact_refs=list(artifact_refs or []),
                )
                s.add(row)
                try:
                    await s.commit()
                except IntegrityError:
                    # Same-revision workers can legitimately race here.  The
                    # unique key makes the snapshot first-write-wins; recover
                    # the committed winner instead of failing the work item and
                    # blocking every dependent learner-facing capability.
                    await s.rollback()
                    row = await s.scalar(
                        select(FactSnapshot).where(
                            FactSnapshot.task_id == task_id,
                            FactSnapshot.turn_id == turn_id,
                            FactSnapshot.plan_revision == plan_revision,
                        )
                    )
                    if row is None:
                        raise
            return {
                "id": row.id,
                "facts": dict(row.facts),
                "evidence_refs": list(row.evidence_refs),
                "artifact_refs": list(row.artifact_refs),
            }
''',
    )


def patch_api() -> None:
    path = Path("web/lib/lingxi/api.ts")
    replace_once(
        path,
        '''export function agentTaskV1Events(taskId: string): Promise<{ events: AgentTaskEvent[] }> {
  return request<{ events: AgentTaskEvent[] }>(
    `/agent-tasks/${taskId}/events?format=json&protocol=v1`
  )
}
''',
        '''export function agentTaskV1Events(
  taskId: string,
  from = 0
): Promise<{ events: AgentTaskEvent[] }> {
  return request<{ events: AgentTaskEvent[] }>(
    `/agent-tasks/${taskId}/events?format=json&protocol=v1&last_event_id=${Math.max(0, from)}`
  )
}
''',
    )


def patch_hook() -> None:
    path = Path("web/app/workspace/[workspaceId]/home/hooks/use-lingxi-graph-chat.ts")
    replace_once(
        path,
        '''  const unsubscribeV1Ref = useRef<(() => void) | null>(null)
  const v1ModelRef = useRef<LingxiV1ThreadModel | null>(null)
  const messagesRef = useRef<ChatMessage[]>([])
''',
        '''  const unsubscribeV1Ref = useRef<(() => void) | null>(null)
  const v1ModelRef = useRef<LingxiV1ThreadModel | null>(null)
  // SSE Last-Event-ID belongs to the durable AgentTaskEvent table.  Never use
  // LingxiV1ThreadModel.lastSeq here: that is the protocol envelope sequence.
  const v1RowSequenceRef = useRef(0)
  const messagesRef = useRef<ChatMessage[]>([])
''',
    )
    replace_once(
        path,
        '''    setV1Model(null)
    v1ModelRef.current = null
    setLocalUsers([])
''',
        '''    setV1Model(null)
    v1ModelRef.current = null
    v1RowSequenceRef.current = 0
    setLocalUsers([])
''',
    )
    replace_once(
        path,
        '''    const applyV1Event = (row: AgentTaskEvent) => {
      if (cancelled) return
      const envelope = decodeLingxiMothershipEvent(row.payload)
      if (!envelope) return
''',
        '''    const applyV1Event = (row: AgentTaskEvent) => {
      if (cancelled) return
      const envelope = decodeLingxiMothershipEvent(row.payload)
      if (!envelope) return
      if (typeof row.sequence === 'number') {
        v1RowSequenceRef.current = Math.max(v1RowSequenceRef.current, row.sequence)
      }
''',
    )
    replace_once(
        path,
        '''    const start = async () => {
      try {
''',
        '''    // Attach the live V1 transport before any task/history hydration.
    // Previously the hook waited for several HTTP round trips first, creating
    // a window where the run could emit its opening response before the page
    // was listening.  Starting from zero is safe because the reducer is
    // idempotent and the durable stream replays in order.
    unsubscribeV1Ref.current = subscribeAgentV1Events(taskId, applyV1Event, { from: 0 })

    // Some production proxies/CDNs buffer fetch-based SSE even when the origin
    // sets X-Accel-Buffering: no.  A cheap cursor-based JSON catch-up keeps the
    // mounted page live in that environment, rather than making refresh the
    // only way to observe already-persisted replies.
    let v1CatchUpInFlight = false
    const catchUpV1 = async () => {
      if (cancelled || v1CatchUpInFlight) return
      v1CatchUpInFlight = true
      try {
        const page = await agentTaskV1Events(taskId, v1RowSequenceRef.current)
        for (const row of page.events.sort((a, b) => a.sequence - b.sequence)) {
          applyV1Event(row)
        }
      } catch {
        /* SSE remains the primary transport; retry on the next tick. */
      } finally {
        v1CatchUpInFlight = false
      }
    }
    const v1CatchUpTimer = globalThis.setInterval(() => void catchUpV1(), 1000)

    const start = async () => {
      try {
''',
    )
    replace_once(
        path,
        '''          const v1History = await agentTaskV1Events(taskId)
          if (!cancelled && v1History.events.length > 0) {
            const model = buildV1ThreadModel(
              taskId,
              v1History.events.map((row) => decodeLingxiMothershipEvent(row.payload))
            )
            v1ModelRef.current = model
            setV1Model(model)
          }
''',
        '''          const v1History = await agentTaskV1Events(taskId)
          if (!cancelled && v1History.events.length > 0) {
            const model = buildV1ThreadModel(
              taskId,
              v1History.events.map((row) => decodeLingxiMothershipEvent(row.payload))
            )
            const durableHighWater = Math.max(
              v1RowSequenceRef.current,
              ...v1History.events.map((row) => row.sequence)
            )
            v1RowSequenceRef.current = durableHighWater
            // Do not overwrite a live model that already received a newer
            // envelope while the history request was in flight.
            if (!v1ModelRef.current || v1ModelRef.current.lastSeq <= model.lastSeq) {
              v1ModelRef.current = model
              setV1Model(model)
            }
          }
''',
    )
    replace_once(
        path,
        '''        // The V1 envelope stream drives the per-turn transcript.  It stays
        // open across turns on the long-lived thread (issue #18 §15.1), so
        // per-send resubscription is unnecessary but harmless.
        if (v1ModelRef.current) {
          unsubscribeV1Ref.current = subscribeAgentV1Events(taskId, applyV1Event, {
            from: v1ModelRef.current.lastSeq,
          })
        } else {
          // A chat created before V1 may still emit V1 envelopes once a new
          // turn runs; watch for them and switch over on first arrival.
          unsubscribeV1Ref.current = subscribeAgentV1Events(taskId, (row) => {
            if (!v1ModelRef.current) {
              v1ModelRef.current = emptyV1ThreadModel(taskId)
            }
            applyV1Event(row)
          })
        }
''',
        '''        // V1 was subscribed before hydration above.  Keep that one
        // long-lived subscription; catch-up polling shares the durable row
        // cursor and fills gaps if the network buffers SSE chunks.
''',
    )
    replace_once(
        path,
        '''      unsubscribeV1Ref.current?.()
      unsubscribeV1Ref.current = null
    }
''',
        '''      unsubscribeV1Ref.current?.()
      unsubscribeV1Ref.current = null
      globalThis.clearInterval(v1CatchUpTimer)
    }
''',
    )


def add_tests() -> None:
    backend = Path("server/tests/test_live_stream_regression.py")
    backend.write_text(
        '''from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_v1_json_history_respects_durable_event_cursor() -> None:
    source = (ROOT / "lingxilearn" / "api" / "routes.py").read_text(encoding="utf-8")
    assert "cursor,\n            protocol_version=protocol_version" in source
    assert source.index("header = request.headers.get") < source.index('format") == "json"')


def test_fact_snapshot_insert_race_recovers_committed_winner() -> None:
    source = (ROOT / "lingxilearn" / "store" / "db.py").read_text(encoding="utf-8")
    method = source[source.index("async def save_fact_snapshot"):source.index("# -- knowledge graphs")]
    assert "except IntegrityError:" in method
    assert "await s.rollback()" in method
    assert "FactSnapshot.task_id == task_id" in method
''',
        encoding="utf-8",
    )
    frontend = Path("web/lib/lingxi/live-stream-regression.test.ts")
    frontend.write_text(
        '''import { readFileSync } from 'node:fs'
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
''',
        encoding="utf-8",
    )


if __name__ == "__main__":
    patch_routes()
    patch_db()
    patch_api()
    patch_hook()
    add_tests()
