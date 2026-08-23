import { env, envNumber } from '@/lib/core/config/env'

/** Per-task Trigger.dev concurrency caps. Bound heavy DB tasks so unbounded fan-out can't saturate the pool. */

export const WEBHOOK_EXECUTION_CONCURRENCY_LIMIT = envNumber(
  env.WEBHOOK_EXECUTION_CONCURRENCY_LIMIT,
  75,
  { min: 1, integer: true }
)
