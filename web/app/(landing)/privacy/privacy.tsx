import { ProsePage } from '@/app/(landing)/components/prose-page'
import { PRIVACY_CONFIG } from '@/app/(landing)/privacy/privacy-content'

/**
 * 隐私政策页面只消费共享的 {@link ProsePage} 原语。完整文案集中在
 * {@link PRIVACY_CONFIG} 中，由路由组统一渲染，确保与服务条款保持一致的布局。
 */
export default function Privacy() {
  return <ProsePage config={PRIVACY_CONFIG} />
}
