import type { IdentityMe } from './identity-api'

/** Options for a canonical session revalidation. */
export interface SessionRefreshOptions {
  /**
   * Bypass the provider's freshness window. Reserved for flows that KNOW the
   * session state just changed — login, logout, session-expired recovery, and
   * explicit refresh actions — never for ordinary reads.
   */
  force?: boolean
}

type CanonicalRefresh = (options?: SessionRefreshOptions) => Promise<IdentityMe | null>

let snapshotData: IdentityMe | null = null
let snapshotReady = false
let canonicalRefresh: CanonicalRefresh | null = null

/**
 * Publishes the canonical browser session state. `SessionProvider` is the only
 * publisher: this module never fetches, caches, or revalidates on its own — it
 * is a read-only projection of the provider's state for code that cannot read
 * React context.
 */
export function publishSessionSnapshot(next: { data: IdentityMe | null; ready: boolean }): void {
  snapshotData = next.data
  snapshotReady = next.ready
}

/** Registers the mounted provider's refresh as the canonical revalidation path. */
export function registerCanonicalSessionRefresh(handler: CanonicalRefresh): () => void {
  canonicalRefresh = handler
  return () => {
    if (canonicalRefresh === handler) canonicalRefresh = null
  }
}

/**
 * Synchronous read of the canonical session for imperative (non-React)
 * callers. Returns `null` before the provider settles or when signed out —
 * callers must treat `null` as "no session", never as a reason to fetch `/me`
 * themselves.
 */
export function getSessionSnapshot(): IdentityMe | null {
  return snapshotData
}

/** Whether the provider has completed its first session resolution. */
export function isSessionSnapshotReady(): boolean {
  return snapshotReady
}

/**
 * Explicit revalidation delegated to the mounted `SessionProvider` — the ONE
 * path that may still hit `/api/v1/me`. Falls back to the current snapshot
 * when no provider is mounted (server render, standalone scripts).
 */
export async function refreshCanonicalSession(
  options?: SessionRefreshOptions
): Promise<IdentityMe | null> {
  if (canonicalRefresh) return canonicalRefresh(options)
  return snapshotData
}
