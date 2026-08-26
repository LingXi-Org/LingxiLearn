/**
 * User settings domain client.
 *
 * Owns learner preferences and LingxiLearn-local settings.
 * Issue #40: extracted from the God API object in ``lib/lingxi/api.ts``.
 */

import type { SessionListItem } from '@/lib/lingxi/types'
import { request } from '../transport'

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
