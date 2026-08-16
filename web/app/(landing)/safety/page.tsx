import { buildLandingMetadata } from '@/lib/landing/seo'
import Safety from '@/app/(landing)/safety/safety'

export const revalidate = 3600

const TITLE = '安全与开放 | LingXi 灵犀智学'
const DESCRIPTION =
  '集中查看 LingXi 的运行时架构、数据合规、隐私政策、服务条款、Skills 文档库与 LingxiGraph 开发文档。'

export const metadata = buildLandingMetadata({
  title: TITLE,
  description: DESCRIPTION,
  path: '/safety',
})

export default function Page() {
  return <Safety />
}
