import { buildLandingMetadata } from '@/lib/landing/seo'
import { LEARNING_PAGE_CONFIGS, LearningProductPage } from '@/app/(landing)/learning/learning-pages'

export const revalidate = 3600

export const metadata = buildLandingMetadata({
  title: '学情诊断 · LingXi',
  description: LEARNING_PAGE_CONFIGS['learning-diagnosis'].seoDescription ?? '',
  path: '/learning/diagnosis',
  imageAlt: 'LingXi 学情诊断',
  twitterImageAlt: 'LingXi 学情诊断',
})

export default function Page() {
  return <LearningProductPage slug='learning-diagnosis' />
}
