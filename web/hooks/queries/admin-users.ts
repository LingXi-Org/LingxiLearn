import { createLogger } from '@sim/logger'
import { useMutation } from '@tanstack/react-query'
import { client } from '@/lib/auth/auth-client'

const logger = createLogger('AdminUsersQuery')

/**
 * Ends a Better Auth impersonation session from the workspace chrome banner.
 *
 * The admin console that started impersonations was removed together with the
 * rest of the Sim admin closure (issue #54) — no Lingxi backend owns user
 * administration. This hook stays only because the impersonation banner still
 * mounts from the workspace layout; it retires with the Better Auth residue
 * cleanup (#74).
 */
export function useStopImpersonating() {
  return useMutation({
    mutationFn: async () => {
      const result = await client.admin.stopImpersonating()
      return result
    },
    onError: (err) => {
      logger.error('Failed to stop impersonating', err)
    },
  })
}
