import type { Metadata } from 'next'
import { LINGXI_BRAND_ASSETS } from '@/lib/branding/lingxi-assets'
import {
  HOME_PAGE_DESCRIPTION,
  HOME_PAGE_TITLE,
} from '@/app/(landing)/components/home-structured-data'
import Landing from '@/app/(landing)/landing'

export const revalidate = 3600

export const metadata: Metadata = {
  metadataBase: new URL('https://lingxilearn.cn'),
  title: {
    absolute: HOME_PAGE_TITLE,
  },
  description: HOME_PAGE_DESCRIPTION,
  keywords:
    'AI 学习, 个性化学习, 学习助手, AI 教育, 学习状态, 知识图解, 智能练习, 复习规划, LingXi, 灵犀智学',
  authors: [{ name: '灵犀智学' }],
  creator: '灵犀智学',
  publisher: '灵犀智学',
  formatDetection: {
    email: false,
    address: false,
    telephone: false,
  },
  openGraph: {
    title: HOME_PAGE_TITLE,
    description: HOME_PAGE_DESCRIPTION,
    type: 'website',
    url: 'https://lingxilearn.cn',
    siteName: '灵犀智学',
    locale: 'zh_CN',
    images: [
      {
        url: LINGXI_BRAND_ASSETS.wordmarkOnLight,
        width: 5064,
        height: 2169,
        alt: '灵犀智学，面向学习任务的智能工作台',
        type: 'image/svg+xml',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    site: '@lingxilearn',
    creator: '@lingxilearn',
    title: HOME_PAGE_TITLE,
    description: HOME_PAGE_DESCRIPTION,
    images: {
      url: LINGXI_BRAND_ASSETS.wordmarkOnLight,
      alt: '灵犀智学，面向学习任务的智能工作台',
    },
  },
  alternates: {
    canonical: 'https://lingxilearn.cn',
    languages: {
      'zh-CN': 'https://lingxilearn.cn',
      'x-default': 'https://lingxilearn.cn',
    },
  },
  robots: {
    index: true,
    follow: true,
    nocache: false,
    googleBot: {
      index: true,
      follow: true,
      noimageindex: false,
      'max-video-preview': -1,
      'max-image-preview': 'large',
      'max-snippet': -1,
    },
  },
  category: 'technology',
  classification: 'AI Development Tools',
  referrer: 'origin-when-cross-origin',
}

export default function Page() {
  return <Landing />
}
