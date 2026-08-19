import { describe, expect, it } from 'vitest'
import type { ExecutionLogDetail, ExecutionLogSummary } from '@/lib/api/contracts/logs'
import {
  mapExecutionLogDetail,
  mapExecutionLogSummary,
  mapRunStatus,
  parseRunDurationMs,
  resolveExecutionSource,
  resolveTriggerPresentation,
  UNKNOWN_RUN_SOURCE_LABEL,
  UNTITLED_AGENT_TASK_LABEL,
} from './execution-log-mapper'

function summary(overrides: Partial<ExecutionLogSummary> = {}): ExecutionLogSummary {
  return {
    id: 'log-1',
    workflowId: null,
    executionId: 'execution-1',
    deploymentVersionId: null,
    deploymentVersion: null,
    deploymentVersionName: null,
    executionOrigin: null,
    level: 'info',
    status: 'success',
    duration: '1250ms',
    trigger: 'agent-task',
    createdAt: '2026-08-19T00:00:00.000Z',
    workflow: null,
    jobTitle: 'Research task',
    cost: null,
    pauseSummary: { total: 0, resumed: 0 },
    hasPendingPause: false,
    ...overrides,
  }
}

describe('native execution log mapper', () => {
  it('maps AgentTask and execution identity without requiring a workflow', () => {
    const view = mapExecutionLogSummary(summary())
    expect(view.identity).toEqual({ logId: 'log-1', executionId: 'execution-1' })
    expect(view.source).toEqual({ kind: 'agent-task', title: 'Research task' })
  })

  it('uses stable fallbacks for missing AgentTask and source metadata', () => {
    expect(resolveExecutionSource({ trigger: 'agent-task' }).title).toBe(UNTITLED_AGENT_TASK_LABEL)
    expect(resolveExecutionSource({}).title).toBe(UNKNOWN_RUN_SOURCE_LABEL)
    expect(resolveTriggerPresentation('unknown_provider')).toEqual({
      type: 'unknown_provider',
      label: 'Unknown Provider',
      color: '#6b7280',
    })
  })

  it('normalizes failed and interaction-pause statuses', () => {
    expect(mapRunStatus('failed')).toBe('error')
    expect(mapRunStatus('awaiting_user')).toBe('pending')
    const view = mapExecutionLogSummary(
      summary({ status: 'awaiting_user', pauseSummary: { total: 2, resumed: 1 }, hasPendingPause: true })
    )
    expect(view.pause).toEqual({ total: 2, resumed: 1, hasPending: true })
  })

  it('maps existing wall duration without inventing queue or steering latency', () => {
    expect(parseRunDurationMs({ duration: '1250ms' })).toBe(1250)
    expect(parseRunDurationMs({ totalDurationMs: 42 })).toBe(42)
    expect(parseRunDurationMs({ duration: null })).toBeNull()
  })

  it('passes canonical nested AgentRun and SkillRun trajectory through unchanged', () => {
    const trajectory = {
      version: '1',
      executionId: 'execution-1',
      clock: { startedAt: '2026-08-19T00:00:00.000Z', durationMs: 20 },
      lanes: [
        {
          id: 'control' as const,
          label: 'CONTROL ROUND',
          items: [
            {
              id: 'agent-run-1',
              lane: 'control' as const,
              kind: 'agent-run',
              label: 'AgentRun',
              startTime: '2026-08-19T00:00:00.000Z',
              relativeStartMs: 0,
              durationMs: 20,
              precision: 'exact' as const,
            },
          ],
        },
        {
          id: 'action' as const,
          label: 'ACTION',
          items: [
            {
              id: 'skill-run-1',
              parentId: 'agent-run-1',
              lane: 'action' as const,
              kind: 'skill-run',
              label: 'SkillRun',
              startTime: '2026-08-19T00:00:00.005Z',
              relativeStartMs: 5,
              durationMs: 10,
              precision: 'exact' as const,
            },
          ],
        },
      ],
    }
    const detail = {
      ...summary(),
      executionData: { enhanced: true as const, workflowInput: { taskId: 'task-1' }, trajectory },
      files: null,
      costLedger: null,
    } satisfies ExecutionLogDetail
    const view = mapExecutionLogDetail(detail)
    expect(view.taskId).toBe('task-1')
    expect(view.trajectory).toBe(trajectory)
    expect(view.trajectory?.lanes[1].items[0].parentId).toBe('agent-run-1')
  })
})
