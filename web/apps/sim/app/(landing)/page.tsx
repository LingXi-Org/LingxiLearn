import type { Metadata } from 'next'
import { SITE_URL } from '@/lib/core/utils/urls'
import {
  HOME_PAGE_DESCRIPTION,
  HOME_PAGE_TITLE,
} from '@/app/(landing)/components/home-structured-data'
import Landing from '@/app/(landing)/landing'

export const revalidate = 3600

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    absolute: HOME_PAGE_TITLE,
  },
  description: HOME_PAGE_DESCRIPTION,
  keywords:
    'AI 工作空间, AI 智能体构建器, AI 智能体工作流构建器, 构建 AI 智能体, 可视化工作流构建器, 开源 AI 智能体平台, AI 智能体, 智能体工作流, LLM 编排, AI 自动化, 知识库, 工作流构建器, AI 集成, SOC2, 企业级 AI',
  authors: [{ name: 'Sim' }],
  creator: 'Sim',
  publisher: 'Sim',
  formatDetection: {
    email: false,
    address: false,
    telephone: false,
  },
  openGraph: {
    title: HOME_PAGE_TITLE,
    description: HOME_PAGE_DESCRIPTION,
    type: 'website',
    url: SITE_URL,
    siteName: 'Sim',
    locale: 'zh_CN',
    images: [
      {
        url: '/logo/426-240/reverse/small.png',
        width: 2130,
        height: 1200,
        alt: 'Sim，面向团队的 AI 工作空间',
        type: 'image/png',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    site: '@simdotai',
    creator: '@simdotai',
    title: HOME_PAGE_TITLE,
    description: HOME_PAGE_DESCRIPTION,
    images: {
      url: '/logo/426-240/reverse/small.png',
      alt: 'Sim，面向团队的 AI 工作空间',
    },
  },
  alternates: {
    canonical: SITE_URL,
    languages: {
      'zh-CN': SITE_URL,
      'x-default': SITE_URL,
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
