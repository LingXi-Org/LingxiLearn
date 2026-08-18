'use client'

import { useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import type { SettingsSection } from '@/app/workspace/[workspaceId]/settings/navigation'

const SETTINGS_RETURN_URL_KEY = 'settings-return-url'

interface SettingsNavigationOptions {
  section?: SettingsSection
  mcpServerId?: string
  browserView?: 'passwords'
  browserImport?: boolean
  browserClear?: boolean
}

interface UseSettingsNavigationReturn {
  navigateToSettings: (options?: SettingsNavigationOptions) => void
  getSettingsHref: (options?: SettingsNavigationOptions) => string
  popSettingsReturnUrl: (fallback: string) => string
}

interface ResolveSettingsHrefParams {
  options?: SettingsNavigationOptions
  workspaceId?: string
}

export function resolveSettingsHref({ options, workspaceId }: ResolveSettingsHrefParams): string {
  if (!workspaceId) return '/workspace'
  // Billing is not an integrated LingxiLearn capability (issue #54): the
  // section no longer resolves to a billing or upgrade surface, it lands on
  // the general settings page like any other removed section.
  const section = options?.section && options.section !== 'billing' ? options.section : 'general'

  const searchParams = new URLSearchParams()
  if (options?.mcpServerId) searchParams.set('mcpServerId', options.mcpServerId)
  if (options?.browserView) searchParams.set('browserView', options.browserView)
  if (options?.browserImport) searchParams.set('browserImport', '1')
  if (options?.browserClear) searchParams.set('browserClear', '1')
  const query = searchParams.toString()
  const pathname = `/workspace/${workspaceId}/settings/${section}`
  return query ? `${pathname}?${query}` : pathname
}

export function useSettingsNavigation(): UseSettingsNavigationReturn {
  const router = useRouter()
  const params = useParams<{ workspaceId?: string }>()
  const workspaceId = params.workspaceId

  const settingsPrefix = `/workspace/${workspaceId}/settings/`

  const getSettingsHref = useCallback(
    (options?: SettingsNavigationOptions): string =>
      resolveSettingsHref({
        options,
        workspaceId,
      }),
    [workspaceId]
  )

  const popSettingsReturnUrl = useCallback((fallback: string): string => {
    try {
      const url = sessionStorage.getItem(SETTINGS_RETURN_URL_KEY)
      sessionStorage.removeItem(SETTINGS_RETURN_URL_KEY)
      return url ?? fallback
    } catch {
      return fallback
    }
  }, [])

  const navigateToSettings = useCallback(
    (options?: SettingsNavigationOptions) => {
      const currentPath = window.location.pathname
      if (currentPath.startsWith(settingsPrefix)) {
        router.replace(getSettingsHref(options), { scroll: false })
      } else {
        try {
          sessionStorage.setItem(SETTINGS_RETURN_URL_KEY, currentPath)
        } catch {}
        router.push(getSettingsHref(options))
      }
    },
    [router, settingsPrefix, getSettingsHref]
  )

  return { navigateToSettings, getSettingsHref, popSettingsReturnUrl }
}
