'use client'

import type { BrandConfig, OrganizationWhitelabelSettings } from '@/lib/branding/types'
import { getBrandConfig } from '@/ee/whitelabeling'

interface BrandingProviderProps {
  children: React.ReactNode
  hostOrganizationId: string | null
  viewerIsHostOrganizationMember: boolean
  initialOrgSettings?: OrganizationWhitelabelSettings | null
}

export function BrandingProvider({ children }: BrandingProviderProps) {
  return children
}

export function useOrgBrandConfig(): BrandConfig {
  return getBrandConfig()
}
