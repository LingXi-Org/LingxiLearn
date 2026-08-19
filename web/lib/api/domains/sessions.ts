/**
 * Sessions domain client.
 *
 * Owns session creation, snapshots, answers, reports, artifacts, and
 * event streams. Issue #40: extracted from ``lib/lingxi/api.ts``.
 */

import type { RunEvent, SessionSnapshot } from '@/lib/lingxi/types'
import { request, fetchArtifactBlob } from '../transport'
import { subscribeSse } from '../transport/sse'
import { API_BASE } from '@/lib/api/config'
import type { SseOptions } from '../transport/sse'

// ---------------------------------------------------------------------------
// CRUD
// ---------------------------------------------------------------------------

export function createSession(missionId: string, packId = '') {
  return request<{ id: string; mission_id: string; pack_id: string; status: string }>(
    '/sessions',
    { method: 'POST', body: JSON.stringify({ mission_id: missionId, pack_id: packId }) }
  )
}

export function getSession(id: string) {
  return request<SessionSnapshot>(`/sessions/${id}`)
}

export function submitAnswer(id: string, answer: unknown) {
  return request<{ status: string }>(`/sessions/${id}/answer`, {
    method: 'POST',
    body: JSON.stringify({ answer }),
  })
}

export function getSessionReport(id: string) {
  return request<Record<string, unknown>>(`/sessions/${id}/report`)
}

// ---------------------------------------------------------------------------
// Artifacts
// ---------------------------------------------------------------------------

export function artifactUrl(sessionId: string, artifactId: string): string {
  return `${API_BASE}/api/sessions/${sessionId}/artifact/${artifactId}`
}

export { fetchArtifactBlob }

// ---------------------------------------------------------------------------
// Events (SSE)
// ---------------------------------------------------------------------------

export function subscribeSessionEvents(
  sessionId: string,
  onEvent: (event: RunEvent) => void,
  options: SseOptions = {}
): () => void {
  return subscribeSse(`/sessions/${sessionId}/events`, onEvent, options)
}
