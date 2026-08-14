import { buildLandingMetadata } from '@/lib/landing/seo'
import Terms from '@/app/(landing)/terms/terms'

export const revalidate = 3600

const TITLE = '服务条款 | LingXi 灵犀智学'
const DESCRIPTION = 'LingXi（灵犀智学）学习工作台、智能体任务、知识库和相关服务的使用条款。'

export const metadata = buildLandingMetadata({
  title: TITLE,
  description: DESCRIPTION,
  path: '/terms',
})

export default function Page() {
  return <Terms />
}
