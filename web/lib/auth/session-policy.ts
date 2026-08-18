import { db } from '@sim/db'
import type { SessionPolicySettings } from '@sim/db/schema'
import { organization } from '@sim/db/schema'
import { createLogger } from '@sim/logger'
import { eq, sql } from 'drizzle-orm'
import { MIN_IDLE_TIMEOUT_HOURS } from '@/lib/api/contracts/organization'
import { isOrganizationFeatureEntitled } from '@/lib/billing/core/subscription'
import { isSessionPoliciesEnabled } from '@/lib/core/config/env-flags'

const logger = createLogger('SessionPolicy')

/** How long a resolved org session policy is served from process memory. */
const SESSION_POLICY_CACHE_TTL_MS = 60 * 1000

export interface ResolvedSessionPolicy {
  maxSessionHours: number | null
  idleTimeoutHours: number | null
}

interface PolicyCacheEntry {
  policy: ResolvedSessionPolicy
  fetchedAt: number
}

const policyCache = new Map<string, PolicyCacheEntry>()

const NO_POLICY: ResolvedSessionPolicy = {
  maxSessionHours: null,
  idleTimeoutHours: null,
}

/**
 * Resolves the EFFECTIVE session policy for an organization, served from a
 * short TTL cache. Returns a no-op policy for personal (org-less) orgs and —
 * mirroring data-retention's plan-gated effective settings — for hosted orgs
 * no longer on an Enterprise plan: stored limits stop enforcing automatically
 * on downgrade, since the enterprise-gated settings UI can no longer manage
 * them.
 */
export async function getSessionPolicy(
  organizationId: string | null | undefined
): Promise<ResolvedSessionPolicy> {
  if (!organizationId) return NO_POLICY

  const cached = policyCache.get(organizationId)
  if (cached && Date.now() - cached.fetchedAt < SESSION_POLICY_CACHE_TTL_MS) {
    return cached.policy
  }

  try {
    const [row] = await db
      .select({ settings: organization.sessionPolicySettings })
      .from(organization)
      .where(eq(organization.id, organizationId))
      .limit(1)

    const settings: SessionPolicySettings = row?.settings ?? {}
    const hasBounds = Boolean(settings.maxSessionHours || settings.idleTimeoutHours)
    const isEntitled =
      !hasBounds || (await isOrganizationFeatureEntitled(organizationId, isSessionPoliciesEnabled))
    const policy: ResolvedSessionPolicy = isEntitled
      ? {
          maxSessionHours: settings.maxSessionHours ?? null,
          idleTimeoutHours: settings.idleTimeoutHours ?? null,
        }
      : NO_POLICY
    policyCache.set(organizationId, { policy, fetchedAt: Date.now() })
    return policy
  } catch (error) {
    logger.error('Failed to resolve session policy; applying no policy', {
      organizationId,
      error,
    })
    return NO_POLICY
  }
}

/**
 * Applies the org's session policy to a user who just JOINED the org:
 * clamps their pre-join sessions, which otherwise keep their old expiry
 * until the next sliding refresh. Best-effort by design — a failure here must
 * never fail the join.
 */
export async function applySessionPolicyToNewMember(
  userId: string,
  organizationId: string
): Promise<void> {
  try {
    const policy = await getSessionPolicy(organizationId)
    const bounds = clampBoundsSql(policy)
    if (!bounds) return

    await db.execute(sql`
      UPDATE "session" SET expires_at = LEAST(${bounds})
      WHERE user_id = ${userId} AND impersonated_by IS NULL
    `)
  } catch (error) {
    logger.error('Failed to apply session policy to new member; next refresh re-clamps', {
      userId,
      organizationId,
      error,
    })
  }
}

/** SQL argument list for the LEAST() clamp, or null when the policy is empty. */
function clampBoundsSql(policy: ResolvedSessionPolicy) {
  const bounds = [sql`expires_at`]
  if (policy.maxSessionHours) {
    const maxSecs = policy.maxSessionHours * 3600
    bounds.push(sql`created_at + make_interval(secs => ${maxSecs})`)
  }
  if (policy.idleTimeoutHours) {
    const idleSecs = Math.max(policy.idleTimeoutHours, MIN_IDLE_TIMEOUT_HOURS) * 3600
    bounds.push(sql`now() + make_interval(secs => ${idleSecs})`)
  }
  if (bounds.length === 1) return null
  return sql.join(bounds, sql`, `)
}
