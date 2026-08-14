import type { MetadataRoute } from 'next'
import { LINGXI_BRAND_ASSETS } from '@/lib/branding/lingxi-assets'

export const dynamic = 'force-static'
export const revalidate = 3600

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: '灵犀智学',
    short_name: '灵犀',
    description: '灵犀智学基于 LingxiGraph，为学习任务提供连续对话、课程资源和知识检测。',
    start_url: '/',
    scope: '/',
    display: 'standalone',
    background_color: '#ffffff',
    theme_color: '#111111',
    orientation: 'portrait-primary',
    icons: [
      {
        src: LINGXI_BRAND_ASSETS.faviconDarkCircle,
        type: 'image/x-icon',
      },
      {
        src: LINGXI_BRAND_ASSETS.faviconLight,
        type: 'image/x-icon',
      },
    ],
    categories: ['productivity', 'developer', 'business'],
    shortcuts: [
      {
        name: '开始学习',
        short_name: '开始',
        description: '创建一个新的学习任务',
        url: '/workspace/lingxi/home',
      },
    ],
    lang: 'zh-CN',
    dir: 'ltr',
  }
}
