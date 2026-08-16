import { buildLandingMetadata } from '@/lib/landing/seo'
import { LEARNING_PAGE_CONFIGS, LearningProductPage } from '@/app/(landing)/learning/learning-pages'

export const revalidate = 3600

export const metadata = buildLandingMetadata({
  title: `${LEARNING_PAGE_CONFIGS['learning-loop'].module} · LingXi`,
  description: LEARNING_PAGE_CONFIGS['learning-loop'].seoDescription ?? '',
  path: '/learning',
  imageAlt: 'LingXi 学习闭环',
  twitterImageAlt: 'LingXi 学习闭环',
})

export default function Page() {
  return <LearningProductPage slug='learning-loop' />
}
