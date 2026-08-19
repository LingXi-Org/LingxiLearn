import { z } from 'zod'
import { defineRouteContract } from '@/lib/api/contracts/types'

export const schedulePermissionDecisionSchema = z.enum([
  'allow',
  'allow_chat',
  'always_allow',
  'skip',
])

export const schedulePermissionBodySchema = z.object({
  decisions: z
    .array(
      z.object({
        proposalId: z.string().min(1, 'Proposal ID is required'),
        decision: schedulePermissionDecisionSchema,
      })
    )
    .min(1, 'At least one decision is required')
    .max(50, 'Too many decisions in one request'),
})

export const schedulePermissionContract = defineRouteContract({
  method: 'POST',
  path: '/api/agent-interactions/schedule-permissions',
  body: schedulePermissionBodySchema,
  response: {
    mode: 'json',
    schema: z.object({
      success: z.literal(true),
      results: z.array(
        z.object({
          proposalId: z.string(),
          decision: schedulePermissionDecisionSchema,
          applied: z.boolean(),
        })
      ),
    }),
  },
})
