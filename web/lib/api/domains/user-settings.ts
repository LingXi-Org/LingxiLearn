/**
 * User settings domain client.
 *
 * Owns profile, preferences, billing, and usage operations.
 * Issue #40: extracted from the God API object in ``lib/lingxi/api.ts``.
 */

import type { SessionListItem } from '@/lib/lingxi/types'
import { request } from '../transport'

// ---------------------------------------------------------------------------
// Profile
// ---------------------------------------------------------------------------

export function getUserProfile() {
  return request<{ user: Record<string, unknown> }>('/users/me/profile')
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

export function getUserSettings() {
  return request<{ data: Record<string, unknown> }>('/users/me/settings')
}

export function updateUserSettings(patch: Record<string, unknown>) {
  return request<{ success: boolean; data?: Record<string, unknown> }>('/users/me/settings', {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
}

// ---------------------------------------------------------------------------
// Context / Mastery / Preferences
// ---------------------------------------------------------------------------

export function getContext() {
  return request<{
    profile: Record<string, unknown>
    mastery: Record<string, number>
    misconceptions: Record<string, unknown>[]
    preferences: Record<string, unknown>
  }>('/me/context')
}

export function getMastery() {
  return request<{ mastery: Record<string, number>; sessions: SessionListItem[] }>('/me/mastery')
}

export function getPreferences() {
  return request<{ preferences: Record<string, unknown> }>('/me/preferences')
}

export function updatePreferences(patch: Record<string, unknown>) {
  return request<{ preferences: Record<string, unknown> }>('/me/preferences', {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
}

// ---------------------------------------------------------------------------
// Billing (read-only / no-op for Lingxi private workspace)
// ---------------------------------------------------------------------------

export function getBilling() {
  return request<{ success: boolean; context: string; data: Record<string, unknown> }>(
    '/billing?context=user&includeOrg=false'
  )
}

export function getBillingInvoices(context: 'user' | 'organization' = 'user') {
  return request<{
    success: boolean
    invoices: Array<Record<string, unknown>>
    hasMore: boolean
  }>(`/billing/invoices?context=${context}`)
}

export function getBillingPortal(returnUrl = '/workspace/lingxi/settings/billing') {
  return request<{ url: string }>('/billing/portal', {
    method: 'POST',
    body: JSON.stringify({ context: 'user', returnUrl }),
  })
}

export function purchaseCredits(amount: number) {
  return request<{ success: boolean; message?: string }>('/billing/credits', {
    method: 'POST',
    body: JSON.stringify({ amount, requestId: crypto.randomUUID() }),
  })
}

export function switchBillingPlan(targetPlanName: string, interval: 'month' | 'year' = 'month') {
  return request<{ success: boolean; plan?: string; interval?: string; message?: string }>(
    '/billing/switch-plan',
    { method: 'POST', body: JSON.stringify({ targetPlanName, interval }) }
  )
}

export function getBillingUsageLimits() {
  return request<{
    success: boolean
    rateLimit: Record<string, unknown>
    usage: Record<string, unknown>
    storage: Record<string, unknown>
  }>('/users/me/usage-limits')
}

export function getV2BillingStatus(workspaceId = 'lingxi') {
  return request<{ data: Record<string, unknown> }>(
    `/v2/billing/status?workspaceId=${encodeURIComponent(workspaceId)}`
  )
}

export function getV2BillingLogs(
  params: {
    period?: '1d' | '7d' | '30d' | 'all' | 'custom'
    startDate?: string
    endDate?: string
    source?: string
    cursor?: string
    limit?: number
  } = {}
) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries({ workspaceId: 'lingxi', ...params })) {
    if (value !== undefined && value !== '') query.set(key, String(value))
  }
  return request<{ data: Array<Record<string, unknown>>; nextCursor: string | null }>(
    `/v2/billing/logs?${query.toString()}`
  )
}

export function getUsageLogs(period = '30d') {
  return request<{
    success: boolean
    logs: Array<Record<string, unknown>>
    summary: { totalCredits: number; bySourceCredits: Record<string, number> }
    pagination: { nextCursor?: string | null; hasMore: boolean }
  }>(`/users/me/usage-logs?period=${encodeURIComponent(period)}`)
}
