import { createLandingOgImage } from '@/app/(landing)/og-utils'

export const dynamic = 'force-static'
export const revalidate = 3600
export const contentType = 'image/png'
export const size = {
  width: 1200,
  height: 630,
}

export function generateStaticParams() {
  return [{ token: 'lingxi' }]
}

/**
 * Social-preview card for a shared file. Public shares show the file name +
 * provenance; protected (password / email / SSO) and unknown shares stay generic
 * so the filename never leaks pre-auth.
 */
export default function Image() {
  return createLandingOgImage({
    eyebrow: '灵犀分享',
    title: '分享内容 · 未接入',
    subtitle: '该分享入口尚未接入 LingxiGraph',
  })
}
