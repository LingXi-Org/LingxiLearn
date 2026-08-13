import type { MetadataRoute } from 'next'
import { SITE_URL } from '@/lib/urls'

export const dynamic = 'force-static'
export const revalidate = 86400

const DISALLOWED_PATHS = [
  '/api/',
  '/workspace/',
  '/playground/',
  '/resume/',
  '/invite/',
  '/unsubscribe/',
  '/w/',
  '/_next/',
  '/private/',
]

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: '*', allow: '/', disallow: DISALLOWED_PATHS },
    sitemap: [
      `${SITE_URL}/sitemap.xml`,
      `${SITE_URL}/blog/sitemap-images.xml`,
      `${SITE_URL}/library/sitemap-images.xml`,
    ],
  }
}
