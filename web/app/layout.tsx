import type { Metadata, Viewport } from 'next'
import { NuqsAdapter } from 'nuqs/adapters/next/app'
import '@/app/_styles/globals.css'
import { LINGXI_BRAND_ASSETS } from '@/lib/branding/lingxi-assets'
import { LingxiIdentityProvider } from '@/lib/lingxi/lingxi-identity-provider'
import { QueryProvider } from '@/app/_shell/providers/query-provider'
import { season } from '@/app/_styles/fonts/season/season'

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#ffffff' },
    { media: '(prefers-color-scheme: dark)', color: '#0c0c0c' },
  ],
}

export const metadata: Metadata = {
  metadataBase: new URL('https://lingxilearn.cn'),
  title: {
    default: '灵犀智学',
    template: '%s · 灵犀智学',
  },
  description: '面向学习任务的 LingxiGraph 智能学习工作台。',
  applicationName: '灵犀智学',
  icons: {
    icon: [
      {
        url: LINGXI_BRAND_ASSETS.faviconLight,
        media: '(prefers-color-scheme: light)',
        type: 'image/x-icon',
      },
      {
        url: LINGXI_BRAND_ASSETS.faviconDark,
        media: '(prefers-color-scheme: dark)',
        type: 'image/x-icon',
      },
    ],
    apple: LINGXI_BRAND_ASSETS.faviconDarkCircle,
  },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang='zh-CN' suppressHydrationWarning>
      <head>
        <meta name='color-scheme' content='light dark' />
        <meta name='format-detection' content='telephone=no' />
      </head>
      <body className={`${season.variable} font-body`} suppressHydrationWarning>
        <NuqsAdapter>
          <QueryProvider>
            <LingxiIdentityProvider>{children}</LingxiIdentityProvider>
          </QueryProvider>
        </NuqsAdapter>
      </body>
    </html>
  )
}
