export interface BrandConfig {
  name: string
  logoUrl?: string
  wordmarkUrl?: string
  faviconUrl?: string
  supportEmail?: string
  documentationUrl?: string
  termsUrl?: string
  privacyUrl?: string
  customCssUrl?: string
  theme?: {
    primaryColor?: string
    primaryHoverColor?: string
    accentColor?: string
    accentHoverColor?: string
    backgroundColor?: string
  }
  isWhitelabeled: boolean
}

const LINGXI_BRAND: BrandConfig = {
  name: 'Lingxi',
  logoUrl: '/logo_icon_black.svg',
  wordmarkUrl: '/logo_icon_black.svg',
  faviconUrl: '/favicon.ico',
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

export function getBrandConfig(): BrandConfig {
  return LINGXI_BRAND
}

export function useBrandConfig(): BrandConfig {
  return LINGXI_BRAND
}
