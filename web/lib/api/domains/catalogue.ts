/**
 * Catalogue domain client.
 *
 * Owns health check, packs, and skills catalogue operations.
 * Issue #40: extracted from the God API object in ``lib/lingxi/api.ts``.
 */

import type { NativeSkill, Pack } from '@/lib/lingxi/types'
import { request } from '../transport'

export function getHealth() {
  return request<{
    status: string
    brain: string
    agent: { configured: boolean; model: string }
    packs: string[]
    tools: number
  }>('/health')
}

export function getPacks() {
  return request<{ packs: Pack[] }>('/packs')
}

export function getSkills() {
  return request<{ skills: NativeSkill[] }>('/skills')
}

export function createSkill(body: {
  name: string
  description?: string
  content?: string
  version?: string
}) {
  return request<{ skill: NativeSkill }>('/skills', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function updateSkill(skillId: string, body: Record<string, string>) {
  return request<{ skill: NativeSkill }>(`/skills/${encodeURIComponent(skillId)}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

export function deleteSkill(skillId: string) {
  return request<{ success: boolean }>(`/skills/${encodeURIComponent(skillId)}`, {
    method: 'DELETE',
  })
}
