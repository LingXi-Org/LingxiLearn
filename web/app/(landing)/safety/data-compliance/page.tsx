import { buildLandingMetadata } from '@/lib/landing/seo'
import { ProsePage } from '@/app/(landing)/components/prose-page'
import { DATA_COMPLIANCE_CONFIG } from '@/app/(landing)/safety/data-compliance/data-compliance-content'

export const revalidate = 3600

export const metadata = buildLandingMetadata({
  title: '数据来源与合规说明 | LingXi 灵犀智学',
  description:
    'LingXi 使用的数据类型、来源和授权状态，以及脱敏、权限、删除、教育边界、依赖披露与运行证据说明。',
  path: '/safety/data-compliance',
})

export default function Page() {
  return <ProsePage config={DATA_COMPLIANCE_CONFIG} />
}
