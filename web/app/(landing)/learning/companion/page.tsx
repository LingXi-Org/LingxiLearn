import { buildLandingMetadata } from '@/lib/landing/seo'
import { LEARNING_PAGE_CONFIGS, LearningProductPage } from '@/app/(landing)/learning/learning-pages'

export const revalidate = 3600

export const metadata = buildLandingMetadata({
  title: '学习陪伴 · LingXi',
  description: LEARNING_PAGE_CONFIGS['learning-companion'].seoDescription ?? '',
  path: '/learning/companion',
  imageAlt: 'LingXi 学习陪伴',
  twitterImageAlt: 'LingXi 学习陪伴',
})

export default function Page() {
  return <LearningProductPage slug='learning-companion' />
}
