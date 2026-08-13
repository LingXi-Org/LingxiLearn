import { buildLandingMetadata } from '@/lib/landing/seo'
import { LEARNING_PAGE_CONFIGS, LearningProductPage } from '@/app/(landing)/learning/learning-pages'

export const revalidate = 3600

export const metadata = buildLandingMetadata({
  title: '作业辅导 · Lingxi',
  description: LEARNING_PAGE_CONFIGS['homework-support'].seoDescription ?? '',
  path: '/learning/homework',
  imageAlt: 'Lingxi 作业辅导',
  twitterImageAlt: 'Lingxi 作业辅导',
})

export default function Page() {
  return <LearningProductPage slug='homework-support' />
}
