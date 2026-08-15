import { BuildCallout } from '@/app/(landing)/components/features/components/build-callout/build-callout'
import { FeatureCard } from '@/app/(landing)/components/features/components/feature-card'
import { IntegrationsCallout } from '@/app/(landing)/components/features/components/integrations-callout/integrations-callout'
import { KnowledgeCallout } from '@/app/(landing)/components/features/components/knowledge-callout/knowledge-callout'
import { LogsCallout } from '@/app/(landing)/components/features/components/logs-callout'

/**
 * Landing features - how LingXi works, as a learning lifecycle. Four beats, in
 * the order a learner needs them: bring in resources, understand the current
 * state, learn and practice, then review progress. Each beat is a
 * Cursor-style {@link FeatureCard}: one large
 * outlined card holding a media stage (backdrop painting + elevated real-UI
 * callout) and a copy column, with the media side alternating card to card.
 *
 * The section's `<h2>` is `sr-only` - each beat carries its own visible `<h3>`,
 * so the section heading exists only to anchor the heading hierarchy and give AI
 * crawlers an atomic summary.
 *
 * Inter-section spacing is owned by the `<main>` flex `gap` in `landing.tsx`;
 * this section carries no vertical padding. The section itself is FULL-WIDTH so
 * its bottom rule can bleed to the browser edges; the card grid inside carries
 * the shared gutter (`px-20`) and the `max-w-[1460px]` cap. The last card
 * squares its bottom corners (`flushBottom`) and sits exactly on the rule, so
 * its outline merges into the full-bleed divider.
 *
 * The cards stack in a single column at every width on a 112px rhythm
 * (matching Cursor's spacing between feature cards). Below `lg` each card
 * internally reflows media-over-copy.
 *
 * Per-beat icons are still abstract placeholders (text eyebrows); distinct
 * abstract glyphs land in a later pass.
 */
export function Features() {
  return (
    <section id='features' aria-labelledby='features-heading' className='relative w-full'>
      <h2 id='features-heading' className='sr-only'>
        了解目标、组织内容、进行练习并持续复习。
      </h2>

      <div className='mx-auto grid w-full max-w-[1460px] grid-cols-1 gap-28 px-20 max-sm:gap-12 max-sm:px-5 max-lg:px-8'>
        {/* Resources: bring learning materials in. */}
        <FeatureCard
          eyebrow='资源'
          title='把你的学习材料放在一起。'
          description='整理课程、笔记、文档和错题，让每一次讲解与练习都建立在你的学习上下文之上。'
          href='/library'
          linkLabel='查看学习资源'
          backdropSrc='/landing/feature-integrate-backdrop.jpg'
        >
          <IntegrationsCallout />
        </FeatureCard>

        {/* State: keep the learner context useful. */}
        <FeatureCard
          eyebrow='状态'
          title='让学习状态真正参与下一步。'
          description='LingXi 关注你的目标、进度、错误和掌握情况，为每一次讲解、练习和复习提供更合适的上下文。'
          backdropSrc='/landing/feature-context-backdrop.jpg'
          mediaSide='right'
        >
          <KnowledgeCallout />
        </FeatureCard>

        {/* Learn: explain and practice. */}
        <FeatureCard
          eyebrow='学习'
          title='从讲解走到真正会做。'
          description='多智能体协作组织概念讲解、知识图解、分层练习和即时反馈，让学习过程随着你的回答持续调整。'
          href='/learning'
          linkLabel='探索学习闭环'
        >
          <BuildCallout />
        </FeatureCard>

        {/* Review: keep improving. */}
        <FeatureCard
          eyebrow='复习'
          title='把每次练习变成下一步建议。'
          description='回顾学习记录、测试结果和薄弱知识点，持续更新你的复习重点与学习路径。'
          backdropSrc='/landing/feature-monitor-backdrop.jpg'
          mediaSide='right'
          flushBottom
        >
          <LogsCallout />
        </FeatureCard>
      </div>

      {/* Full-bleed rule the last card's squared bottom edge merges into -
          spans the whole browser, past the content cap and gutter (the section
          itself is full-width; only the card grid above is capped). */}
      <div aria-hidden='true' className='absolute inset-x-0 bottom-0 h-px bg-[var(--border)]' />
    </section>
  )
}
