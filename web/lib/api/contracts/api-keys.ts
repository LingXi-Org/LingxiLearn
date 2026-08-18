import { z } from 'zod'
import { defineRouteContract } from '@/lib/api/contracts/types'

const apiKeyMetadataSchema = z.object({
  id: z.string(),
  name: z.string(),
  lastUsed: z.string().nullable().optional(),
  createdAt: z.string(),
  expiresAt: z.string().nullable().optional(),
  createdBy: z.string().nullable().optional(),
})

export const apiKeyListItemSchema = apiKeyMetadataSchema.extend({
  displayKey: z.string(),
})

export const apiKeySchema = apiKeyMetadataSchema.extend({
  key: z.string(),
  displayKey: z.string().optional(),
})

export type ApiKey = z.output<typeof apiKeyListItemSchema>
export type CreatedApiKey = z.output<typeof apiKeySchema>

export const createApiKeyBodySchema = z.object({
  name: z.string().trim().min(1, 'Name is required'),
  source: z.enum(['settings', 'deploy_modal']).optional(),
})

export const createPersonalApiKeyBodySchema = createApiKeyBodySchema.pick({ name: true })

const workspaceApiKeyParamsSchema = z.object({
  id: z.string().min(1),
})

// The api-keys settings surfaces were removed with their capability decision
// (issue #54): neither endpoint has a Lingxi backend owner. The list and
// create contracts stay for the workflow MCP servers surface, which reads
// existing key names and mints workspace keys through CreateApiKeyModal.
// The delete/update contracts had no other caller and stay removed.
export const listPersonalApiKeysContract = defineRouteContract({
  method: 'GET',
  path: '/api/users/me/api-keys',
  response: {
    mode: 'json',
    schema: z.object({
      keys: z.array(apiKeyListItemSchema),
    }),
  },
})

export const listWorkspaceApiKeysContract = defineRouteContract({
  method: 'GET',
  path: '/api/workspaces/[id]/api-keys',
  params: workspaceApiKeyParamsSchema,
  response: {
    mode: 'json',
    schema: z.object({
      keys: z.array(apiKeyListItemSchema),
    }),
  },
})

export const createPersonalApiKeyContract = defineRouteContract({
  method: 'POST',
  path: '/api/users/me/api-keys',
  body: createPersonalApiKeyBodySchema,
  response: {
    mode: 'json',
    schema: z.object({
      key: apiKeySchema,
    }),
  },
})

export const createWorkspaceApiKeyContract = defineRouteContract({
  method: 'POST',
  path: '/api/workspaces/[id]/api-keys',
  params: workspaceApiKeyParamsSchema,
  body: createApiKeyBodySchema,
  response: {
    mode: 'json',
    schema: z.object({
      key: apiKeySchema,
    }),
  },
})
