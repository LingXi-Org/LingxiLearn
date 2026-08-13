import type { Metadata } from 'next'
import type { BrandConfig, ThemeColors } from '@/lib/branding/types'

const LINGXI_BRAND: BrandConfig = {
  name: 'Lingxi',
  logoUrl: '/logo_icon_black.svg',
  wordmarkUrl: '/logo_icon_black.svg',
  faviconUrl: '/favicon.ico',
  supportEmail: undefined,
  documentationUrl: undefined,
  termsUrl: '/terms',
  privacyUrl: '/privacy',
  theme: {
    primaryColor: '#171717',
    primaryHoverColor: '#2b2b2b',
    accentColor: '#171717',
    accentHoverColor: '#2b2b2b',
    backgroundColor: '#0c0c0c',
  },
  isWhitelabeled: true,
}

export type { BrandConfig, ThemeColors }
export type { OrganizationWhitelabelSettings } from '@/lib/branding/types'

export function getBrandConfig(): BrandConfig {
  return LINGXI_BRAND
}

export function useBrandConfig(): BrandConfig {
  return LINGXI_BRAND
}

export function generateThemeCSS(): string {
  return ':root{--brand-primary:#171717;--brand-accent:#171717}'
}

export function generateBrandedMetadata(): Metadata {
  return {
    title: '灵犀智学',
    description: '基于 LingxiGraph 的智能学习工作区',
  }
}

export function generateStructuredData(): Record<string, string> {
  return { '@context': 'https://schema.org', '@type': 'SoftwareApplication', name: 'Lingxi' }
}

export function generateOrgThemeCSS(): string {
  return ''
}

export function mergeOrgBrandConfig(): BrandConfig {
  return LINGXI_BRAND
}
