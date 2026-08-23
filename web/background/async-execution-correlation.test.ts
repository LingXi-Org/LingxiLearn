/**
 * @vitest-environment node
 */

import { describe, expect, it } from 'vitest'
import {
  describeRetryableInfrastructureError,
  isRetryableInfrastructureError,
} from '@/lib/core/errors/retryable-infrastructure'
import { buildWebhookCorrelation } from '@/background/webhook-execution'

describe('async execution correlation fallbacks', () => {
  it('classifies retryable driver causes without treating every failed query as retryable', () => {
    const driverError = Object.assign(new Error('remaining connection slots are reserved'), {
      code: '53300',
    })
    const drizzleError = new Error('Failed query: select * from "environment"', {
      cause: driverError,
    })

    expect(isRetryableInfrastructureError(drizzleError)).toBe(true)
    expect(describeRetryableInfrastructureError(drizzleError)).toEqual(
      expect.objectContaining({
        code: '53300',
        message: 'remaining connection slots are reserved',
      })
    )
    expect(
      isRetryableInfrastructureError(new Error('remaining connection slots are reserved'))
    ).toBe(false)
    expect(
      isRetryableInfrastructureError(
        Object.assign(new Error('connect failed'), { code: 'ETIMEDOUT' })
      )
    ).toBe(true)
    expect(isRetryableInfrastructureError(new Error('Failed query: syntax error'))).toBe(false)
  })

  it('falls back for legacy webhook payloads missing preassigned fields', () => {
    const correlation = buildWebhookCorrelation({
      webhookId: 'webhook-1',
      workflowId: 'workflow-1',
      userId: 'user-1',
      executionId: 'webhook-exec-1',
      provider: 'slack',
      body: {},
      headers: {},
      path: 'incoming/slack',
    })

    expect(correlation).toEqual({
      executionId: 'webhook-exec-1',
      requestId: 'webhook-',
      source: 'webhook',
      workflowId: 'workflow-1',
      webhookId: 'webhook-1',
      path: 'incoming/slack',
      provider: 'slack',
      triggerType: 'webhook',
    })
  })
})
