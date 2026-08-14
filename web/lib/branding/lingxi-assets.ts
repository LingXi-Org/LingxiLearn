/**
 * Canonical Lingxi brand assets.
 *
 * The suffix describes the surface the asset is placed on, not the color mode
 * of the browser. Keeping that distinction explicit prevents a white mark from
 * being placed on a light surface (or the inverse) during future UI work.
 */
export const LINGXI_BRAND_ASSETS = {
  wordmarkOnLight: '/brand/lingxi/wordmark-on-light.svg',
  wordmarkOnDark: '/brand/lingxi/wordmark-on-dark.svg',
  iconOnLight: '/brand/lingxi/icon-on-light.svg',
  iconOnDark: '/brand/lingxi/icon-on-dark.svg',
  faviconLight: '/brand/lingxi/favicon-light.ico',
  faviconDark: '/brand/lingxi/favicon-dark.ico',
  faviconDarkCircle: '/brand/lingxi/favicon-dark-circle.ico',
} as const
