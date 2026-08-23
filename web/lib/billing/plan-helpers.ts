import {
  CREDIT_TIERS,
  DEFAULT_PRO_TIER_COST_LIMIT,
  DEFAULT_TEAM_TIER_COST_LIMIT,
  MAX_TIER_CREDITS,
} from '@/lib/billing/constants'

export type PlanCategory = 'free' | 'pro' | 'team' | 'enterprise'

export const isPro = (plan: string | null | undefined): boolean =>
  plan === 'pro' || Boolean(plan?.startsWith('pro_'))
export const isTeam = (plan: string | null | undefined): boolean =>
  plan === 'team' || Boolean(plan?.startsWith('team_'))
export const isFree = (plan: string | null | undefined): boolean => !plan || plan === 'free'
export const isEnterprise = (plan: string | null | undefined): boolean => plan === 'enterprise'
export const isPaid = (plan: string | null | undefined): boolean =>
  isPro(plan) || isTeam(plan) || isEnterprise(plan)
export const isOrgPlan = (plan: string | null | undefined): boolean =>
  isTeam(plan) || isEnterprise(plan)

export function getPlanTierCredits(plan: string | null | undefined): number {
  const match = plan?.match(/_(\d+)$/)
  if (match) return Number.parseInt(match[1], 10)
  if (plan === 'pro') return 4000
  if (plan === 'team') return 8000
  return 0
}

export const isMaxTier = (plan: string | null | undefined): boolean =>
  getPlanTierCredits(plan) >= MAX_TIER_CREDITS || isEnterprise(plan)

export function getPlanTierDollars(plan: string | null | undefined): number {
  const tier = CREDIT_TIERS.find((item) => item.credits === getPlanTierCredits(plan))
  if (tier) return tier.dollars
  if (plan === 'pro') return DEFAULT_PRO_TIER_COST_LIMIT
  if (plan === 'team') return DEFAULT_TEAM_TIER_COST_LIMIT
  return 0
}

export function getPlanType(plan: string | null | undefined): PlanCategory {
  if (isPro(plan)) return 'pro'
  if (isTeam(plan)) return 'team'
  if (isEnterprise(plan)) return 'enterprise'
  return 'free'
}

export function getPlanTypeForLimits(plan: string | null | undefined): PlanCategory {
  if (plan === 'pro' || plan === 'team') return getPlanType(plan)
  if (isPro(plan) || isTeam(plan)) return isMaxTier(plan) ? 'team' : 'pro'
  return getPlanType(plan)
}

export const buildPlanName = (type: 'pro' | 'team', credits: number): string =>
  `${type}_${credits}`
export const getValidPlanNames = (type: 'pro' | 'team'): string[] =>
  CREDIT_TIERS.map((tier) => buildPlanName(type, tier.credits))

export function getDisplayPlanName(plan: string | null | undefined): string {
  if (isFree(plan)) return 'Free'
  if (isEnterprise(plan)) return 'Enterprise'
  const tier = CREDIT_TIERS.find((item) => item.credits === getPlanTierCredits(plan))
  const tierName = tier?.name ?? (plan === 'team' ? 'Max' : 'Pro')
  return `${plan === 'pro' || plan === 'team' ? 'Legacy ' : ''}${tierName}${
    isTeam(plan) ? ' for Teams' : ''
  }`
}
