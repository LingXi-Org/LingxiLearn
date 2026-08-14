import { buildLandingMetadata } from '@/lib/landing/seo'
import { LEARNING_PAGE_CONFIGS, LearningProductPage } from '@/app/(landing)/learning/learning-pages'

export const revalidate = 3600

export const metadata = buildLandingMetadata({
  title: '疑难讲解 · LingXi',
  description: LEARNING_PAGE_CONFIGS.explanation.seoDescription ?? '',
  path: '/learning/explanation',
  imageAlt: 'LingXi 疑难讲解',
  twitterImageAlt: 'LingXi 疑难讲解',
})

export default function Page() {
  return <LearningProductPage slug='explanation' />
}
