import { buildLandingMetadata } from '@/lib/landing/seo'
import Privacy from '@/app/(landing)/privacy/privacy'

export const revalidate = 3600

const TITLE = '隐私政策 | LingXi 灵犀智学'
const DESCRIPTION =
  'LingXi（灵犀智学）如何处理账户、学习任务、知识资源和智能体运行相关信息，以及用户和监护人的数据权利。'

export const metadata = buildLandingMetadata({
  title: TITLE,
  description: DESCRIPTION,
  path: '/privacy',
})

export default function Page() {
  return <Privacy />
}
