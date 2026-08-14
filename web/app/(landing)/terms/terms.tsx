import { ProsePage } from '@/app/(landing)/components/prose-page'
import { TERMS_CONFIG } from '@/app/(landing)/terms/terms-content'

/**
 * 服务条款页面只消费共享的 {@link ProsePage} 原语。完整文案集中在
 * {@link TERMS_CONFIG} 中，由路由组统一渲染，确保与隐私政策保持一致的布局。
 */
export default function Terms() {
  return <ProsePage config={TERMS_CONFIG} />
}
