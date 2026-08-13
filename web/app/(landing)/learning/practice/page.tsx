import { buildLandingMetadata } from '@/lib/landing/seo'
import { LEARNING_PAGE_CONFIGS, LearningProductPage } from '@/app/(landing)/learning/learning-pages'

export const revalidate = 3600

export const metadata = buildLandingMetadata({
  title: '自适应练习 · Lingxi',
  description: LEARNING_PAGE_CONFIGS['adaptive-practice'].seoDescription ?? '',
  path: '/learning/practice',
  imageAlt: 'Lingxi 自适应练习',
  twitterImageAlt: 'Lingxi 自适应练习',
})

export default function Page() {
  return <LearningProductPage slug='adaptive-practice' />
}
