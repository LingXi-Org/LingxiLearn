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
    'AI 工作空间, AI 智能体构建器, AI 智能体工作流构建器, 构建 AI 智能体, 可视化工作流构建器, 开源 AI 智能体平台, AI 智能体, 智能体工作流, LLM 编排, AI 自动化, 知识库, 工作流构建器, AI 集成, SOC2, 企业级 AI',
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
