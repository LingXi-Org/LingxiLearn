import { buildLandingMetadata } from '@/lib/landing/seo'
import { LEARNING_PAGE_CONFIGS, LearningProductPage } from '@/app/(landing)/learning/learning-pages'

export const revalidate = 3600

export const metadata = buildLandingMetadata({
  title: `${LEARNING_PAGE_CONFIGS['personalized-learning'].module} · Lingxi`,
  description: LEARNING_PAGE_CONFIGS['personalized-learning'].seoDescription ?? '',
  path: '/learning/personalized',
  imageAlt: 'Lingxi 个性化学习',
  twitterImageAlt: 'Lingxi 个性化学习',
})

export default function Page() {
  return <LearningProductPage slug='personalized-learning' />
}
