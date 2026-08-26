/** Lingxi-native observability client. */

import { request } from '@/lib/api/transport/http'

export function getLogs() {
  return request<{ data: Array<Record<string, unknown>> }>('/logs?workspaceId=lingxi')
}
