import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: { default: 'LingxiLearn', template: '%s · LingxiLearn' },
  description: 'A durable AI learning workspace.',
  icons: { icon: '/brand/lingxi/favicon.ico' },
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang='en'>
      <body>{children}</body>
    </html>
  )
}
