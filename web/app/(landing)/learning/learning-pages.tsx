import type { ReactNode } from 'react'
import { HeroPlatformLoop } from '@/app/(landing)/components/hero/components/hero-platform-loop'
import { HeroVisual } from '@/app/(landing)/components/hero/components/hero-visual/hero-visual'
import { LandingPreviewMount } from '@/app/(landing)/components/landing-preview/landing-preview-mount'
import { PlatformHeroVisual } from '@/app/(landing)/components/platform-hero-visual'
import { MasteryMapGraphic } from '@/app/(landing)/components/solutions/mastery-map-graphic'
import { SolutionsPage, type SolutionsPageConfig } from '@/app/(landing)/components/solutions-page'
import { AuditTrailGraphic } from '@/app/(landing)/enterprise/components/feature-graphics/audit-trail-graphic'
import { LifecycleGraphic } from '@/app/(landing)/enterprise/components/feature-graphics/lifecycle-graphic'
import {
  type LogField,
  type OutputPair,
  RunMonitoringGraphic,
} from '@/app/(landing)/enterprise/components/feature-graphics/run-monitoring-graphic'
import { StagingGraphic } from '@/app/(landing)/enterprise/components/feature-graphics/staging-graphic'
import { StandardsGraphic } from '@/app/(landing)/enterprise/components/feature-graphics/standards-graphic'
import { KnowledgeHeroLoop } from '@/app/(landing)/knowledge/components/knowledge-hero-loop'
import { FailureAlertGraphic } from '@/app/(landing)/logs/components/feature-graphics/failure-alert-graphic'
import { LogsHeroLoop } from '@/app/(landing)/logs/components/logs-hero-loop'
import { DocumentDraftGraphic } from '@/app/(landing)/solutions/components/feature-graphics/document-draft-graphic'
import { KnowledgeAnswerGraphic } from '@/app/(landing)/solutions/components/feature-graphics/knowledge-answer-graphic'

export type LearningPageSlug =
  | 'personalized-learning'
  | 'explanation'
  | 'homework-support'
  | 'adaptive-practice'
  | 'learning-diagnosis'
  | 'learning-companion'

const EXPERIENCE_CTA = { label: '立即体验', href: '/workspace/lingxi/home' } as const

function preview(view: 'workflow' | 'knowledge' | 'files' | 'tables' | 'logs' = 'workflow') {
  return <LandingPreviewMount autoplay={false} view={view} />
}

function runPanel(
  title: string,
  labels: readonly [string, string, string],
  values: readonly [string, string, string]
) {
  const fields: readonly LogField[] = labels.map((label, index) => ({
    label,
    value: values[index],
    variant: index === 0 ? 'strong' : index === 1 ? 'chip' : 'mono',
  }))
  const outputPairs: readonly [OutputPair, OutputPair] = [
    { key: 'status', value: '"updated"' },
    { key: 'next', value: '"继续学习"' },
  ]
  return <RunMonitoringGraphic title={title} fields={fields} outputPairs={outputPairs} />
}

function stagingPanel(
  title: string,
  headerTag: string,
  changeTag: string,
  changeTitle: string,
  checks: readonly [string, string, string],
  fromLabel: string,
  toLabel: string,
  actionLabel: string
) {
  return (
    <StagingGraphic
      title={title}
      headerTag={headerTag}
      changeTag={changeTag}
      changeTitle={changeTitle}
      attribution='LingXi · 刚刚'
      checks={checks}
      fromLabel={fromLabel}
      toLabel={toLabel}
      actionLabel={actionLabel}
    />
  )
}

function answerPanel(question: string, answer: string, sourceLabel: string) {
  return <KnowledgeAnswerGraphic question={question} answer={answer} sourceLabel={sourceLabel} />
}

function draftPanel(title: string, statusTag: string, footerLabel: string, footerDetail: string) {
  return (
    <DocumentDraftGraphic
      title={title}
      statusTag={statusTag}
      footerLabel={footerLabel}
      footerDetail={footerDetail}
    />
  )
}

function hero(
  heading: string,
  description: string,
  summary: string,
  visual: ReactNode,
  secondaryHref: string
) {
  return {
    eyebrow: '学习体验',
    heading,
    description,
    summary,
    cta: EXPERIENCE_CTA,
    secondaryCta: { label: '查看流程', href: secondaryHref },
    visual: <PlatformHeroVisual>{visual}</PlatformHeroVisual>,
  }
}

const COMMON_FOOTER = {
  primary: EXPERIENCE_CTA,
  secondary: null,
} as const

export const LEARNING_PAGE_CONFIGS: Record<LearningPageSlug, SolutionsPageConfig> = {
  'personalized-learning': {
    module: '个性化学习',
    path: '/learning/personalized',
    language: 'zh-CN',
    showLogos: false,
    seoDescription:
      'LingXi 根据学习目标、知识基础、练习表现与可用时间动态调整学习路径，让每一步都服务于当前最需要掌握的内容。',
    hero: hero(
      '一条会随着你改变的学习路径',
      'LingXi 先理解你的目标、基础与时间，再规划阶段任务；每次练习和反馈都会更新下一步，而不是把所有人放进同一张课程表。',
      'LingXi 根据学习目标、知识基础、练习表现与可用时间动态调整学习路径，让每一步都服务于当前最需要掌握的内容。',
      <HeroPlatformLoop />,
      '#plan'
    ),
    rows: [
      {
        id: 'plan',
        title: '先理解你，再规划路径',
        subtitle: '把目标、基础和时间约束转成可执行的阶段计划，并明确每一步为什么现在值得学。',
        cta: { label: '查看规划逻辑', href: '#plan' },
        cards: [
          {
            title: '目标与约束',
            description: '结合学习目标、可用时间和当前任务，为计划设定清楚的优先级与边界。',
            visual: stagingPanel(
              '本周学习计划',
              '目标已确认',
              '阶段任务',
              '函数基础 → 导数应用',
              ['目标已确认', '学习时间已记录', '先修知识已检查'],
              '当前状态',
              '本周目标',
              '生成路径'
            ),
          },
          {
            title: '起点诊断',
            description: '根据已有学习记录和当前表现估计掌握状态，避免从过易或过难的位置开始。',
            visual: runPanel(
              '学习状态',
              ['函数概念', '图像理解', '导数基础'],
              ['稳定', '待巩固', '未开始']
            ),
          },
          {
            title: '阶段化学习路径',
            description: '将长期目标拆成可完成的小阶段，并把讲解、练习和验证组织成连续任务。',
            visual: <LifecycleGraphic />,
          },
        ],
      },
      {
        id: 'adapt',
        title: '学习过程中持续调整',
        subtitle:
          '计划不是一次生成后固定不变；LingXi 根据新表现更新状态，再选择下一步最合适的动作。',
        cta: { label: '查看动态调整', href: '#adapt' },
        cards: [
          {
            title: '按状态选择下一步',
            description:
              '根据学习状态在讲解、追问、练习和复习之间切换，形成真正的 Agent 任务闭环。',
            visual: preview('workflow'),
          },
          {
            title: '遇到信息不足先确认',
            description:
              '当目标不清、记录不足或结果不确定时，优先提示缺失信息，而不是强行给出学习结论。',
            visual: <FailureAlertGraphic />,
          },
          {
            title: '每次调整都有依据',
            description: '保留关键学习状态与路径变化记录，帮助学生理解“为什么下一步是这个”。',
            visual: <AuditTrailGraphic />,
          },
        ],
      },
    ],
    footerCta: {
      heading: '让下一步，真正适合现在的你',
      description: '从一个真实学习目标开始，让 LingXi 生成并持续调整你的学习路径。',
      ...COMMON_FOOTER,
    },
  },
  explanation: {
    module: '疑难讲解',
    path: '/learning/explanation',
    language: 'zh-CN',
    showLogos: false,
    seoDescription:
      'LingXi 将抽象知识拆成可追问、可验证的分步讲解，并通过知识依据、交互演示和理解检查帮助学生真正掌握概念。',
    hero: hero(
      '把“看不懂”变成一步一步的理解',
      'LingXi 不急着给结论。它先识别你卡住的位置，再组织背景、概念、例子与可交互讲解，并在讲完后确认你是否真的理解。',
      'LingXi 将抽象知识拆成可追问、可验证的分步讲解，并通过知识依据、交互演示和理解检查帮助学生真正掌握概念。',
      <KnowledgeHeroLoop />,
      '#explain'
    ),
    rows: [
      {
        id: 'explain',
        title: '从卡点开始，而不是从标准答案开始',
        subtitle: '先定位疑问，再调用知识与教学能力，把复杂概念拆成适合当前基础的讲解。',
        cta: { label: '查看讲解流程', href: '#explain' },
        cards: [
          {
            title: '先弄清你卡在哪里',
            description: '识别问题中的知识点、已有上下文与真正困惑，避免重复讲已经掌握的部分。',
            visual: answerPanel(
              '为什么这里要先判断单调性？',
              '先确认函数怎样变化，再决定后续推理路径；如果这一步不清楚，后面的结论就没有依据。',
              '概念定位'
            ),
          },
          {
            title: '分步讲解',
            description: '把定义、直觉、推理和例子组织成连续步骤，让学生能在任意一步继续追问。',
            visual: draftPanel(
              '导数为什么能描述变化率？',
              '分步讲解',
              '当前步骤',
              '从平均变化率过渡到瞬时变化率'
            ),
          },
          {
            title: '可交互地追问',
            description:
              '讲解不是静态文章；学生可以围绕当前步骤继续追问，Agent 保留上下文并调整解释方式。',
            visual: preview('knowledge'),
          },
        ],
      },
      {
        id: 'verify',
        title: '讲完之后，确认是否真的理解',
        subtitle: '用追问、短练习和结果验证闭合一次讲解，而不是把“输出结束”当作“学习完成”。',
        cta: { label: '查看理解验证', href: '#verify' },
        cards: [
          {
            title: '即时理解检查',
            description:
              '用一个关键追问或小任务判断学生是否掌握核心概念，再决定继续还是换一种讲法。',
            visual: stagingPanel(
              '理解检查',
              '讲解完成',
              '关键追问',
              '你能用自己的话解释变化率吗？',
              ['概念已讲解', '例子已完成', '等待理解验证'],
              '讲解',
              '验证',
              '回答'
            ),
          },
          {
            title: '依据与来源可追溯',
            description: '涉及知识检索时保留来源和处理依据，让讲解不是不可解释的黑盒输出。',
            visual: <AuditTrailGraphic />,
          },
          {
            title: '根据理解结果继续',
            description: '掌握不足就换角度重讲或补基础，掌握稳定则进入针对性练习和迁移任务。',
            visual: preview('workflow'),
          },
        ],
      },
    ],
    footerCta: {
      heading: '把一个真正困住你的问题交给 LingXi',
      description: '从“哪里不懂”开始，而不是从标准答案开始。',
      ...COMMON_FOOTER,
    },
  },
  'homework-support': {
    module: '作业辅导',
    path: '/learning/homework',
    language: 'zh-CN',
    showLogos: false,
    seoDescription:
      'LingXi 通过分步骤提示、错因分析、知识点回顾和同类题训练辅导作业，帮助学生自己完成推理，而不是直接生成标准答案。',
    hero: hero(
      '提示、分析，而不是代替你思考',
      '面对作业问题，LingXi 先判断你已经做到哪一步，再给恰到好处的提示、错因分析和知识回顾；目标是帮助你完成推理，而不是把答案直接交给你。',
      'LingXi 通过分步骤提示、错因分析、知识点回顾和同类题训练辅导作业，帮助学生自己完成推理，而不是直接生成标准答案。',
      <HeroPlatformLoop />,
      '#guide'
    ),
    rows: [
      {
        id: 'guide',
        title: '把“不会做”拆成下一步能做什么',
        subtitle: '辅导从学生已有过程开始，尽量给最小必要提示，让思考仍然由学生完成。',
        cta: { label: '查看分步辅导', href: '#guide' },
        cards: [
          {
            title: '先看你的已有过程',
            description: '理解题目、已写步骤和当前卡点，避免跳过学生已经完成的思考。',
            visual: preview('workflow'),
          },
          {
            title: '给下一步提示',
            description: '先提示关键观察、公式选择或检查方向；只有在必要时才逐步增加解释。',
            visual: answerPanel(
              '我卡在第二步，接下来该看什么？',
              '先比较两边是否能化成同一类表达式，再决定是移项还是因式分解。',
              '下一步提示'
            ),
          },
          {
            title: '不把标准答案当默认输出',
            description:
              '对作业辅导保持明确教育边界：优先提示、追问和反馈，避免替代学生完成整道题。',
            visual: <StandardsGraphic />,
          },
        ],
      },
      {
        id: 'learn-from-error',
        title: '从一道错题，学会一类问题',
        subtitle: '找到错误发生的原因，回到相关知识点，再通过同类训练确认是否已经修正。',
        cta: { label: '查看错因闭环', href: '#learn-from-error' },
        cards: [
          {
            title: '错因分析',
            description:
              '区分概念理解、计算步骤、条件遗漏和方法选择等不同错误类型，给出针对性反馈。',
            visual: <FailureAlertGraphic />,
          },
          {
            title: '知识点回顾',
            description: '只补当前错误真正关联的知识，而不是把整章内容重新讲一遍。',
            visual: draftPanel(
              '本题需要回顾：二次函数顶点形式',
              '针对性回顾',
              '建议',
              '先理解配方，再回到原题'
            ),
          },
          {
            title: '同类题验证',
            description: '生成一个难度接近但表述不同的任务，检查学生是否真的掌握了方法。',
            visual: stagingPanel(
              '同类题训练',
              '错因已识别',
              '迁移验证',
              '换一个条件，再独立完成一次',
              ['原题已复盘', '知识点已回顾', '同类题已生成'],
              '错题',
              '迁移',
              '开始'
            ),
          },
        ],
      },
    ],
    footerCta: {
      heading: '把卡住的那一步交给 LingXi',
      description: '得到下一步提示、错因分析和同类训练，同时保留真正属于你的思考过程。',
      ...COMMON_FOOTER,
    },
  },
  'adaptive-practice': {
    module: '自适应练习',
    path: '/learning/practice',
    language: 'zh-CN',
    showLogos: false,
    seoDescription:
      'LingXi 根据知识掌握度、近期错误与学习目标动态生成训练，并在每次作答后更新下一轮题型、难度和反馈策略。',
    hero: hero(
      '练你真正需要练的，而不是再刷一套题',
      'LingXi 把掌握状态、近期错误和学习目标转成下一组练习；每次作答都会成为新的反馈，让题型、难度和提示随你变化。',
      'LingXi 根据知识掌握度、近期错误与学习目标动态生成训练，并在每次作答后更新下一轮题型、难度和反馈策略。',
      <HeroVisual />,
      '#target'
    ),
    rows: [
      {
        id: 'target',
        title: '根据掌握度选择训练目标',
        subtitle: '先判断当前最值得练的知识点与能力，再决定题型、难度和训练数量。',
        cta: { label: '查看练习生成', href: '#target' },
        cards: [
          {
            title: '读取当前掌握状态',
            description: '结合近期练习表现与历史状态，识别稳定掌握、待巩固和未覆盖的知识点。',
            visual: runPanel('掌握状态', ['基础概念', '典型题', '迁移应用'], ['86%', '68%', '42%']),
          },
          {
            title: '动态调整难度',
            description: '避免长期停留在舒适区，也避免连续给出超出当前基础的任务。',
            visual: stagingPanel(
              '下一组练习',
              '掌握度 68%',
              '难度调整',
              '基础巩固 → 轻量迁移',
              ['近期错误已分析', '目标知识点已选', '难度已调整'],
              '当前',
              '下一组',
              '开始练习'
            ),
          },
          {
            title: '针对性生成训练',
            description: '围绕目标知识点组织不同表述和不同情境的练习，减少机械重复。',
            visual: draftPanel(
              '函数单调性 · 迁移练习',
              '已生成',
              '目标',
              '从图像判断过渡到解析式判断'
            ),
          },
        ],
      },
      {
        id: 'feedback-loop',
        title: '作答之后立即进入下一轮判断',
        subtitle: '每次结果都被用来更新诊断、反馈和下一题，而不是等一整套练习结束后才总结。',
        cta: { label: '查看反馈闭环', href: '#feedback-loop' },
        cards: [
          {
            title: '错误后给针对性反馈',
            description:
              '区分偶发失误与稳定薄弱点；需要时先提示，再决定是否降低难度或回到知识讲解。',
            visual: <FailureAlertGraphic />,
          },
          {
            title: '在练习、讲解与复习之间切换',
            description:
              '根据实时状态重新规划下一步，让 Agent 能结束一条无效路径并选择更合适的教学动作。',
            visual: preview('workflow'),
          },
          {
            title: '保留训练与调整记录',
            description: '展示题目选择、反馈和难度变化的关键记录，让自适应过程可以复盘。',
            visual: <AuditTrailGraphic />,
          },
        ],
      },
    ],
    footerCta: {
      heading: '少刷一点，多练真正薄弱的地方',
      description: '从当前掌握状态开始，让每一道练习都有明确目的。',
      ...COMMON_FOOTER,
    },
  },
  'learning-diagnosis': {
    module: '学情诊断',
    path: '/learning/diagnosis',
    language: 'zh-CN',
    showLogos: false,
    seoDescription:
      'LingXi 将练习记录、测试结果与学习过程转成可解释的知识掌握诊断，识别薄弱点、关联关系和下一步改进建议。',
    hero: hero(
      '看见薄弱点，也看见它为什么出现',
      'LingXi 不只给一个分数。它把练习、测试和学习过程组织成知识状态，识别薄弱点与关联，并把诊断转成下一步可执行的学习建议。',
      'LingXi 将练习记录、测试结果与学习过程转成可解释的知识掌握诊断，识别薄弱点、关联关系和下一步改进建议。',
      <LogsHeroLoop />,
      '#diagnose'
    ),
    rows: [
      {
        id: 'diagnose',
        title: '把学习记录变成可行动的诊断',
        subtitle: '从过程数据中寻找稳定模式，而不是用一次作答定义学生。',
        cta: { label: '查看诊断方法', href: '#diagnose' },
        cards: [
          {
            title: '汇总学习证据',
            description: '组织练习记录、测试结果与模拟学习数据，为诊断提供清晰输入和适用边界。',
            visual: preview('tables'),
          },
          {
            title: '识别稳定薄弱信号',
            description: '结合多次表现区分偶发失误与持续薄弱，避免把单次错误直接等同于能力结论。',
            visual: runPanel(
              '诊断信号',
              ['错误重复度', '提示依赖', '迁移表现'],
              ['高', '中', '待加强']
            ),
          },
          {
            title: '知识掌握关系图',
            description: '同时展示多个知识点的掌握度与先修关系，帮助理解薄弱点如何相互影响。',
            visual: <MasteryMapGraphic />,
          },
        ],
      },
      {
        id: 'act',
        title: '诊断的终点，是下一步行动',
        subtitle: '把发现转成可以执行的学习建议，同时保留依据、风险边界和人工判断空间。',
        cta: { label: '查看改进建议', href: '#act' },
        cards: [
          {
            title: '结论附带依据',
            description: '关键诊断保留数据来源、时间和处理记录，便于回看结论从哪里来。',
            visual: <AuditTrailGraphic />,
          },
          {
            title: '生成具体改进动作',
            description:
              '把薄弱点转成复习、讲解、练习或重新验证等下一步，而不是只输出一份静态报告。',
            visual: stagingPanel(
              '下一步建议',
              '诊断完成',
              '优先改进',
              '先巩固函数图像，再进入导数应用',
              ['薄弱点已定位', '先修关系已检查', '下一步已生成'],
              '诊断',
              '行动',
              '开始学习'
            ),
          },
          {
            title: '诊断不替代教育评价',
            description:
              '学习诊断用于辅助学习路径与教学决策，不替代教师、学校或专业机构的最终教育评价。',
            visual: <StandardsGraphic />,
          },
        ],
      },
    ],
    footerCta: {
      heading: '从“哪里薄弱”走到“下一步怎么学”',
      description: '用可解释的学习证据，换来更具体、更可执行的改进路径。',
      ...COMMON_FOOTER,
    },
  },
  'learning-companion': {
    module: '学习陪伴',
    path: '/learning/companion',
    language: 'zh-CN',
    showLogos: false,
    seoDescription:
      'LingXi 在持续对话中保留学习目标、阶段进度与关键学习状态，让每次回来都能从上一次的上下文继续，并推动下一步学习行动。',
    hero: hero(
      '每次回来，都从你的学习进度继续',
      'LingXi 记住的不是闲聊，而是学习目标、阶段任务、关键困难和已经完成的进度。你不必每次重新解释，它会从当前状态继续推动下一步。',
      'LingXi 在持续对话中保留学习目标、阶段进度与关键学习状态，让每次回来都能从上一次的上下文继续，并推动下一步学习行动。',
      <HeroPlatformLoop />,
      '#continue'
    ),
    rows: [
      {
        id: 'continue',
        title: '保留真正有用的学习上下文',
        subtitle: '把长期对话中的目标、进度与关键状态变成可继续执行的学习上下文。',
        cta: { label: '查看上下文管理', href: '#continue' },
        cards: [
          {
            title: '记住学习目标与关键状态',
            description: '保留对后续学习真正有用的信息，而不是把所有历史对话无差别塞进上下文。',
            visual: <AuditTrailGraphic />,
          },
          {
            title: '从上次进度继续',
            description: '再次进入时先呈现当前阶段、未完成任务和最近薄弱点，减少重复说明。',
            visual: <LifecycleGraphic />,
          },
          {
            title: '对话始终围绕学习目标',
            description:
              '学生可以自然提问、反馈和改变节奏，Agent 根据上下文决定直接回答还是进入讲解、练习或诊断。',
            visual: preview('knowledge'),
          },
        ],
      },
      {
        id: 'progress',
        title: '陪伴不是闲聊，而是持续推动学习',
        subtitle: '每次交互都应帮助学生理解当前状态、完成下一步并更新后续计划。',
        cta: { label: '查看学习闭环', href: '#progress' },
        cards: [
          {
            title: '始终给出清楚的下一步',
            description:
              '根据目标和进度在继续讲解、开始练习、复习薄弱点或结束本次学习之间做出选择。',
            visual: <LifecycleGraphic />,
          },
          {
            title: '持续更新学习状态',
            description:
              '把每次理解检查、练习结果和学生反馈回写为新的状态，让后续交互更贴合当前水平。',
            visual: runPanel(
              '本周学习状态',
              ['阶段进度', '薄弱点', '待验证内容'],
              ['4/6', '函数图像', '导数应用']
            ),
          },
          {
            title: '保持教育辅助边界',
            description:
              '学习陪伴用于解释、提醒、反馈和规划，不替代教师教学判断、学校评价或专业教育服务。',
            visual: <StandardsGraphic />,
          },
        ],
      },
    ],
    footerCta: {
      heading: '不用每次从头开始',
      description: '让下一次对话，直接接着你的目标、进度和真正的学习问题继续。',
      ...COMMON_FOOTER,
    },
  },
}

interface LearningProductPageProps {
  slug: LearningPageSlug
}

export function LearningProductPage({ slug }: LearningProductPageProps) {
  return <SolutionsPage config={LEARNING_PAGE_CONFIGS[slug]} />
}
