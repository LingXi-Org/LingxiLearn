import { BuildCallout } from '@/app/(landing)/components/features/components/build-callout/build-callout'
import { FeatureCard } from '@/app/(landing)/components/features/components/feature-card'
import { IntegrationsCallout } from '@/app/(landing)/components/features/components/integrations-callout/integrations-callout'
import { KnowledgeCallout } from '@/app/(landing)/components/features/components/knowledge-callout/knowledge-callout'
import { LogsCallout } from '@/app/(landing)/components/features/components/logs-callout'

/**
 * Landing features - how Sim works, as a platform lifecycle. Four beats, in the
 * order you actually use Sim: bring your tools in (Integrate), give it data to
 * reason over (Context), build the agent logic (Build), then watch it run
 * (Monitor). Each beat is a Cursor-style {@link FeatureCard}: one large
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
        集成工具、提供上下文、构建智能体并监控每次运行。
      </h2>

      <div className='mx-auto grid w-full max-w-[1460px] grid-cols-1 gap-28 px-20 max-sm:gap-12 max-sm:px-5 max-lg:px-8'>
        {/* Integrate: bring your stack in. */}
        <FeatureCard
          eyebrow='集成'
          title='连接工作所依赖的工具。'
          description='接入 Slack、HubSpot、Salesforce、Notion 等 1,000+ 个集成，让 Sim 智能体在你现有的工具链中执行任务。'
          href='/integrations'
          linkLabel='探索集成'
          backdropSrc='/landing/feature-integrate-backdrop.jpg'
        >
          <IntegrationsCallout />
        </FeatureCard>

        {/* Context: store data semantically. */}
        <FeatureCard
          eyebrow='上下文'
          title='让 Sim 使用可推理的数据。'
          description='Sim 将数据存储在数据表、文件和知识库中，作为智能体读取的语义记忆，为每个回答提供可靠依据。'
          backdropSrc='/landing/feature-context-backdrop.jpg'
          mediaSide='right'
        >
          <KnowledgeCallout />
        </FeatureCard>

        {/* Build: wire agent logic in the visual builder. */}
        <FeatureCard
          eyebrow='构建'
          title='构建解决真实问题的智能体。'
          description='在 Sim 的可视化构建器中，将模块、模型和集成编排成智能体逻辑；从单个智能体到多个并行协作的智能体都可以。'
          href='/workflows'
          linkLabel='探索 AI 工作流构建器'
        >
          <BuildCallout />
        </FeatureCard>

        {/* Monitor: watch every run. */}
        <FeatureCard
          eyebrow='监控'
          title='端到端监控每次运行。'
          description='Sim 按模块追踪每次运行，提供完整日志和真实成本。'
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
