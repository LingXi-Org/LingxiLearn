import { BuildCallout } from '@/app/(landing)/components/features/components/build-callout/build-callout'
import { FeatureCard } from '@/app/(landing)/components/features/components/feature-card'
import { IntegrationsCallout } from '@/app/(landing)/components/features/components/integrations-callout/integrations-callout'
import { KnowledgeCallout } from '@/app/(landing)/components/features/components/knowledge-callout/knowledge-callout'

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
        {/* Visualization: turn abstract knowledge into something learners can see. */}
        <FeatureCard
          eyebrow='可视化'
          title='将抽象知识转化为直观的学习体验。'
          description='AI 自动生成交互式课件、知识图解、动态演示与练习题卡，让复杂概念被看见、被理解、被掌握。'
          href='/library'
          linkLabel='查看学习资源'
          backdropSrc='/landing/feature-integrate-backdrop.jpg'
        >
          <IntegrationsCallout />
        </FeatureCard>

        {/* Understanding: keep the learner context useful. */}
        <FeatureCard
          eyebrow='理解'
          title='持续记忆每位学生的学习上下文'
          description='所有行动基于个性化的学习档案、历史交互与知识状态，理解学生当前水平、薄弱点与学习目标。'
          backdropSrc='/landing/feature-context-backdrop.jpg'
          mediaSide='right'
        >
          <KnowledgeCallout />
        </FeatureCard>

        {/* Collaboration: let specialized agents work together. */}
        <FeatureCard
          eyebrow='协作'
          title='多智能体协同完成学习任务'
          description='多个专业 Agent 根据学习目标自动组合，以 Skill 为能力单元并行协作，生成讲义、可视化解释、练习与学习反馈。'
          href='/learning'
          linkLabel='探索学习闭环'
        >
          <BuildCallout />
        </FeatureCard>

        {/* Growth: keep improving. */}
        <FeatureCard
          eyebrow='成长'
          title='持续追踪学习过程与效果'
          description='实时分析学习过程中的反馈、理解程度与知识掌握变化，让 AI 根据学生状态动态调整教学策略。'
          backdropSrc='/landing/feature-context-backdrop.jpg'
          mediaSide='right'
          flushBottom
        >
          <KnowledgeCallout />
        </FeatureCard>
      </div>

      {/* Full-bleed rule the last card's squared bottom edge merges into -
          spans the whole browser, past the content cap and gutter (the section
          itself is full-width; only the card grid above is capped). */}
      <div aria-hidden='true' className='absolute inset-x-0 bottom-0 h-px bg-[var(--border)]' />
    </section>
  )
}
