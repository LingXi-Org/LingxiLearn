import { buildLandingMetadata } from '@/lib/landing/seo'
import { LEARNING_PAGE_CONFIGS, LearningProductPage } from '@/app/(landing)/learning/learning-pages'

export const revalidate = 3600

export const metadata = buildLandingMetadata({
  title: '学习陪伴 · Lingxi',
  description: LEARNING_PAGE_CONFIGS['learning-companion'].seoDescription ?? '',
  path: '/learning/companion',
  imageAlt: 'Lingxi 学习陪伴',
  twitterImageAlt: 'Lingxi 学习陪伴',
})

export default function Page() {
  return <LearningProductPage slug='learning-companion' />
}
