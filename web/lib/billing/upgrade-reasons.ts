/**
 * Upgrade-reason registry.
 *
 * Single source of truth for the language shown when a user is routed to the
 * upgrade page after hitting a usage limit, and for where that route points.
 * The same copy drives both the upgrade-page header and the threshold/limit
 * emails, so the in-app and email journeys never drift apart.
 */
import { SITE_URL } from '@/lib/core/utils/urls'

/** The limit categories that can route a user to the upgrade page. */
export const UPGRADE_REASONS = ['credits', 'storage', 'tables', 'seats'] as const

export type UpgradeReason = (typeof UPGRADE_REASONS)[number]

/** URL query key the upgrade page reads to resolve the reason. */
export const UPGRADE_REASON_PARAM = 'reason' as const

/** Header shown on the upgrade page when no (or an invalid) reason is present. */
export const DEFAULT_UPGRADE_HEADER = 'Plans that scale with you' as const

interface UpgradeReasonCopy {
  /** Upgrade-page `<h1>` header. */
  header: string
  /** Lowercase noun for the limited resource (e.g. "tables", "storage"). */
  noun: string
  /** Subject line for the 80% warning email. */
  warningSubject: string
  /** Subject line for the 100% limit-reached email. */
  reachedSubject: string
  /** One-line body lead for the warning email (running low). */
  warningLead: string
  /** One-line body lead for the limit-reached email. */
  reachedLead: string
}

/**
 * Per-reason copy. Headers follow the "Upgrade to scale ..." pattern; email
 * subjects/leads reuse the same noun so a user sees consistent language whether
 * they arrive from the app or from an email.
 */
export const UPGRADE_REASON_COPY: Record<UpgradeReason, UpgradeReasonCopy> = {
  credits: {
    header: 'Upgrade to scale your usage',
    noun: 'credits',
    warningSubject: "You're nearing your usage limit",
    reachedSubject: "You've reached your usage limit",
    warningLead: "You're approaching your usage limit.",
    reachedLead: "You've reached your usage limit.",
  },
  storage: {
    header: 'Upgrade to scale your storage',
    noun: 'storage',
    warningSubject: "You're running low on storage",
    reachedSubject: "You've reached your storage limit",
    warningLead: "You're running low on storage.",
    reachedLead: "You've reached your storage limit.",
  },
  tables: {
    header: 'Upgrade to scale your tables',
    noun: 'table rows',
    warningSubject: "You're running low on table space",
    reachedSubject: "You've reached your table limit",
    warningLead: "You're running low on table space.",
    reachedLead: "You've reached your table limit.",
  },
  seats: {
    header: 'Upgrade to scale with your teammates',
    noun: 'seats',
    warningSubject: "You're running low on seats",
    reachedSubject: "You've used all your seats",
    warningLead: "You're running low on seats for your team.",
    reachedLead: "You've used all the seats on your plan.",
  },
}

/** Type guard for a raw query value against the known reasons. */
export function isUpgradeReason(value: string | null | undefined): value is UpgradeReason {
  return value != null && (UPGRADE_REASONS as readonly string[]).includes(value)
}

/**
 * Build the fallback link for upgrade prompts.
 *
 * Billing/plans are not an integrated LingxiLearn capability (issue #54) and
 * the workspace upgrade route was removed, so upgrade prompts land on the
 * workspace settings page instead of a dead route.
 */
export function buildUpgradeHref(workspaceId: string, _reason?: UpgradeReason): string {
  return `/workspace/${workspaceId}/settings`
}

/**
 * Absolute fallback link for upgrade prompts on the hosted app.
 *
 * Billing/plans are not an integrated LingxiLearn capability (issue #54); the
 * account-scoped `/upgrade` entry was removed, so hosted upgrade prompts point
 * at the account settings surface instead.
 */
export function buildHostedUpgradeUrl(_reason?: UpgradeReason): string {
  return `${SITE_URL}/account/settings`
}

/** Account settings on the hosted app, for raising a usage limit. */
export const HOSTED_BILLING_SETTINGS_URL = `${SITE_URL}/account/settings` as const
