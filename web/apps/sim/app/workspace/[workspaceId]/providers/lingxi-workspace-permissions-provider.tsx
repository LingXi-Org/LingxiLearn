'use client'

/**
 * LingxiGraph has no Sim organization permission API. The copied Sim chrome
 * still expects a provider boundary, so the static workspace supplies an
 * intentionally empty context boundary and keeps unsupported writes disabled.
 */
export function LingxiWorkspacePermissionsProvider({ children }: { children: React.ReactNode }) {
  return children
}
