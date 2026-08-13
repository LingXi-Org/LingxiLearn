import { buildLandingMetadata } from '@/lib/landing/seo'
import { CapabilityPage } from '@/lib/lingxi/components/capability-page'

const TITLE = '更新日志 | 灵犀智学'
const DESCRIPTION = '灵犀智学学习工作台的版本更新与能力接入记录。'

export const metadata = buildLandingMetadata({
  title: TITLE,
  description: DESCRIPTION,
  path: '/changelog',
})

export default function Page() {
  return <CapabilityPage title='更新日志' />
}
