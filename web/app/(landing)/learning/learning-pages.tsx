import type { ReactNode } from 'react'
import { LINGXI_BRAND_ASSETS } from '@/lib/branding/lingxi-assets'
import type { HeroChatLoopContent } from '@/app/(landing)/components/hero/components/hero-chat-loop'
import { HeroPlatformLoop } from '@/app/(landing)/components/hero/components/hero-platform-loop'
import { PlatformHeroVisual } from '@/app/(landing)/components/platform-hero-visual'
import { MasteryMapGraphic } from '@/app/(landing)/components/solutions/mastery-map-graphic'
import { SolutionsPage, type SolutionsPageConfig } from '@/app/(landing)/components/solutions-page'
import {
  type KnowledgeHeroContent,
  KnowledgeHeroLoop,
} from '@/app/(landing)/knowledge/components/knowledge-hero-loop'
import {
  LearningBoundaryGraphic,
  LearningDialogueGraphic,
  type LearningEvidenceEntry,
  LearningEvidenceGraphic,
  LearningFeedbackGraphic,
  type LearningFeedbackRow,
  LearningPathGraphic,
  type LearningPathStep,
  LearningSignalGraphic,
  type LearningSignalKind,
  type LearningStatusField,
  LearningStatusGraphic,
  LearningTransitionGraphic,
} from '@/app/(landing)/learning/components'
import {
  COMPANION_HERO_WORKFLOW,
  HOMEWORK_HERO_WORKFLOW,
  PERSONALIZED_HERO_WORKFLOW,
  PRACTICE_HERO_WORKFLOW,
} from '@/app/(landing)/learning/learning-hero-workflows'
import { type LogsHeroContent, LogsHeroLoop } from '@/app/(landing)/logs/components/logs-hero-loop'

export type LearningPageSlug =
  | 'personalized-learning'
  | 'explanation'
  | 'homework-support'
  | 'adaptive-practice'
  | 'learning-diagnosis'
  | 'learning-companion'

const EXPERIENCE_CTA = { label: '立即体验', href: '/workspace/lingxi/home' } as const

const PERSONALIZED_HERO_CHAT = {
  userMessage: '我准备参加大学线性代数期末，矩阵特征值总是算错，帮我规划复习顺序。',
  replyMessage:
    '我会先定位特征值计算中的具体卡点，再结合你的考试时间安排概念、例题和自测，生成一条会随着练习结果调整的复习路径。',
  followUps: ['确认考试范围', '定位计算卡点', '生成复习路径'],
} as const satisfies HeroChatLoopContent

const HOMEWORK_HERO_CHAT = {
  userMessage: '我的硕士论文里 ANOVA 结果怎么看？我卡在 p 值和效应量的解释。',
  replyMessage:
    '先把统计显著和实际效应分开，再回到你的研究问题解释 p 值与效应量。我会保留论文中的推理，只补当前需要的判断依据。',
  followUps: ['拆解统计结果', '回顾研究方法', '改写结果段落'],
} as const satisfies HeroChatLoopContent

const PRACTICE_HERO_CHAT = {
  userMessage: '我想转做数据分析，先安排一组 SQL 窗口函数练习。',
  replyMessage:
    '我会从真实业务中的排序、分组和累计计算开始，安排一组适合碎片时间完成的练习，再根据每次作答调整下一题。',
  followUps: ['查看岗位目标', '生成 SQL 练习', '调整练习难度'],
} as const satisfies HeroChatLoopContent

const COMPANION_HERO_CHAT = {
  userMessage: '继续上次的学习，我还没完成 A/B 测试置信区间的迁移练习。',
  replyMessage:
    '我会接着你上次的产品分析学习进度，保留已掌握的抽样概念，从置信区间的业务案例练习继续，并在完成后更新下一步。',
  followUps: ['继续未完成任务', '复习薄弱概念', '查看下一步计划'],
} as const satisfies HeroChatLoopContent

const EXPLANATION_HERO_CONTENT = {
  workspaceName: 'LingXi',
  sidebarLocale: 'zh-CN',
  brandIconSrc: LINGXI_BRAND_ASSETS.iconOnLight,
  chats: ['单调性为什么重要', '变化率怎么理解', '导数定义追问', '理解检查记录'],
  workflows: ['问题定位', '分步讲解', '例子演示', '知识依据', '理解检查'],
  title: '疑难讲解',
  createLabel: '新建讲解',
  searchPlaceholder: '搜索知识点与讲解步骤…',
  filterLabel: '筛选',
  sortLabel: '排序',
  headers: ['内容', '步骤', '理解状态', '依据', '更新时间'],
  syncingLabel: '整理中',
  updatedLabel: '已整理',
  rows: [
    {
      name: '当前问题定位',
      documents: '1 个问题',
      documentsSynced: '1 个问题',
      tokens: '2 个知识点',
      tokensSynced: '3 个知识点',
      created: '刚刚',
    },
    {
      name: '分步讲解',
      documents: '4 步',
      tokens: '2 个例子',
      created: '今天',
    },
    {
      name: '交互例子与练习',
      documents: '2 个任务',
      tokens: '待验证',
      created: '今天',
    },
    {
      name: '知识依据',
      documents: '3 条来源',
      tokens: '已关联',
      created: '昨天',
    },
    {
      name: '理解检查记录',
      documents: '1 次检查',
      tokens: '待回看',
      created: '昨天',
    },
  ],
} as const satisfies KnowledgeHeroContent

const DIAGNOSIS_HERO_CONTENT = {
  workspaceName: 'LingXi',
  sidebarLocale: 'zh-CN',
  brandIconSrc: LINGXI_BRAND_ASSETS.iconOnLight,
  chats: ['查看函数图像薄弱点', '本周学习诊断', '导数基础复盘', '生成改进建议'],
  workflows: ['掌握状态评估', '错误信号分析', '知识关系检查', '复习建议生成', '迁移结果验证'],
  title: '学情诊断',
  exportLabel: '导出诊断',
  primaryTab: '诊断记录',
  secondaryTab: '趋势变化',
  searchPlaceholder: '搜索学习诊断…',
  filterLabel: '筛选',
  sortLabel: '排序',
  headers: ['诊断任务', '时间', '状态', '范围', '来源', '耗时'],
  statusLabels: { completed: '已完成', error: '需复核', running: '分析中' },
  liveRow: {
    workflowName: '本次掌握状态诊断',
    date: '今天 10:24',
    triggerLabel: '学习记录',
    runningCost: '—',
    runningDuration: '—',
    completedCost: '12 条记录',
    completedDuration: '1.8s',
  },
  historyRows: [
    {
      workflowName: '函数图像掌握评估',
      date: '今天 09:12',
      status: 'completed',
      cost: '12 条记录',
      triggerLabel: '练习结果',
      duration: '2.4s',
    },
    {
      workflowName: '导数基础诊断',
      date: '昨天 18:48',
      status: 'completed',
      cost: '8 条记录',
      triggerLabel: '阶段测试',
      duration: '5.3s',
    },
    {
      workflowName: '迁移能力复核',
      date: '昨天 16:02',
      status: 'error',
      cost: '需补充',
      triggerLabel: '学习记录',
      duration: '—',
    },
    {
      workflowName: '近期错误信号分析',
      date: '周一 09:00',
      status: 'completed',
      cost: '16 条记录',
      triggerLabel: '作答反馈',
      duration: '3.1s',
    },
  ],
} as const satisfies LogsHeroContent

function preview(view: 'workflow' | 'knowledge' | 'files' | 'tables' | 'logs' = 'workflow') {
  const kind: LearningSignalKind =
    view === 'knowledge' ? 'dialogue' : view === 'tables' ? 'evidence' : 'path'
  return <LearningSignalGraphic kind={kind} />
}

function runPanel(
  title: string,
  labels: readonly [string, string, string],
  values: readonly [string, string, string]
) {
  const fields: readonly LearningStatusField[] = labels.map((label, index) => ({
    label,
    value: values[index],
  }))
  return (
    <LearningStatusGraphic
      title={title}
      fields={fields}
      output={`下一步：${labels[1]} · ${values[1]}`}
    />
  )
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
    <LearningTransitionGraphic
      title={title}
      headerTag={headerTag}
      changeTag={changeTag}
      changeTitle={changeTitle}
      checks={checks}
      fromLabel={fromLabel}
      toLabel={toLabel}
      actionLabel={actionLabel}
    />
  )
}

function answerPanel(question: string, answer: string, sourceLabel: string) {
  return <LearningDialogueGraphic question={question} answer={answer} sourceLabel={sourceLabel} />
}

function draftPanel(title: string, statusTag: string, footerLabel: string, footerDetail: string) {
  return (
    <LearningPathGraphic
      title={title}
      statusLabel={statusTag}
      steps={[
        { label: '当前内容', title: footerLabel, detail: footerDetail, state: 'current' },
        { label: '下一步', title: '继续学习', detail: '根据当前结果更新路径', state: 'next' },
      ]}
    />
  )
}

function pathPanel(title: string, steps: readonly LearningPathStep[]) {
  return <LearningPathGraphic title={title} steps={steps} />
}

function feedbackPanel(title: string, rows: readonly LearningFeedbackRow[], action?: string) {
  return <LearningFeedbackGraphic title={title} rows={rows} action={action} />
}

function evidencePanel(title: string, entries: readonly LearningEvidenceEntry[]) {
  return <LearningEvidenceGraphic title={title} entries={entries} />
}

function boundaryPanel(title: string, leftLabel: string, rightLabel: string, sealLabel: string) {
  return (
    <LearningBoundaryGraphic
      title={title}
      leftLabel={leftLabel}
      rightLabel={rightLabel}
      sealLabel={sealLabel}
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
    pageKind: 'learning',
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
      <HeroPlatformLoop chat={PERSONALIZED_HERO_CHAT} workflow={PERSONALIZED_HERO_WORKFLOW} />,
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
            visual: pathPanel('阶段化学习路径', [
              { label: '阶段 1', title: '函数基础', detail: '当前学习内容', state: 'current' },
              { label: '阶段 2', title: '导数应用', detail: '下一步学习内容', state: 'next' },
              { label: '阶段 3', title: '掌握验证', detail: '完成迁移练习后进入', state: 'past' },
            ]),
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
            visual: feedbackPanel(
              '信息不足，先确认',
              [
                { label: '目标或记录不完整', detail: '暂不生成学习结论' },
                { label: '先补充学习信息', detail: '确认目标与可用时间' },
                { label: '再更新下一步', detail: '继续规划当前阶段' },
              ],
              '补充后继续'
            ),
          },
          {
            title: '每次调整都有依据',
            description: '保留关键学习状态与路径变化记录，帮助学生理解“为什么下一步是这个”。',
            visual: evidencePanel('路径调整依据', [
              { label: '练习表现已记录', detail: '函数图像迁移练习', time: '刚刚' },
              { label: '掌握状态已更新', detail: '图像理解 · 待巩固', time: '2 分钟前' },
              { label: '下一步建议已生成', detail: '补一组同类练习', time: '今天' },
            ]),
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
    pageKind: 'learning',
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
      <KnowledgeHeroLoop content={EXPLANATION_HERO_CONTENT} />,
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
            visual: evidencePanel('讲解依据', [
              { label: '问题与知识点', detail: '单调性与变化率', time: '步骤 1' },
              { label: '解释步骤与例子', detail: '定义 · 直觉 · 推理', time: '步骤 2' },
              { label: '理解结果与下一步', detail: '进入短练习验证', time: '步骤 3' },
            ]),
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
    pageKind: 'learning',
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
      <HeroPlatformLoop chat={HOMEWORK_HERO_CHAT} workflow={HOMEWORK_HERO_WORKFLOW} />,
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
            visual: boundaryPanel('作业辅导边界', '提示下一步', '保留你的推理', '不代写答案'),
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
            visual: feedbackPanel(
              '错误原因已定位',
              [
                { label: '区分概念与计算错误', detail: '当前更接近概念理解问题' },
                { label: '关联需要回顾的知识点', detail: '二次函数顶点形式' },
                { label: '准备同类题验证', detail: '换一种表述再做一次' },
              ],
              '查看针对性反馈'
            ),
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
    pageKind: 'learning',
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
      <HeroPlatformLoop chat={PRACTICE_HERO_CHAT} workflow={PRACTICE_HERO_WORKFLOW} />,
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
            visual: feedbackPanel(
              '错误后立即更新',
              [
                { label: '识别偶发失误', detail: '一次错误，不立即降低难度' },
                { label: '判断稳定薄弱点', detail: '重复出现，回到相关知识' },
                { label: '调整下一道练习', detail: '先提示，再验证迁移' },
              ],
              '进入下一轮判断'
            ),
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
            visual: evidencePanel('训练与调整记录', [
              { label: '题目选择', detail: '函数单调性 · 迁移题', time: '第 1 步' },
              { label: '作答反馈', detail: '提示依赖降低', time: '第 2 步' },
              { label: '难度变化', detail: '基础巩固 → 轻量迁移', time: '第 3 步' },
            ]),
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
    pageKind: 'learning',
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
      <LogsHeroLoop content={DIAGNOSIS_HERO_CONTENT} />,
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
            visual: evidencePanel('诊断依据', [
              { label: '练习记录与测试结果', detail: '近 7 天 · 12 次练习', time: '来源 1' },
              { label: '重复错误信号', detail: '函数图像判断 · 3 次', time: '来源 2' },
              { label: '诊断时间与范围', detail: '本周学习阶段', time: '范围' },
            ]),
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
            visual: boundaryPanel('诊断使用边界', '辅助学习路径', '保留风险与依据', '不替代评价'),
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
    pageKind: 'learning',
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
      <HeroPlatformLoop chat={COMPANION_HERO_CHAT} workflow={COMPANION_HERO_WORKFLOW} />,
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
            visual: evidencePanel('有用的学习上下文', [
              { label: '学习目标', detail: '准备导数应用单元', time: '当前' },
              { label: '阶段进度', detail: '函数基础 · 4/6', time: '进度' },
              { label: '关键困难', detail: '从图像迁移到解析式', time: '待处理' },
            ]),
          },
          {
            title: '从上次进度继续',
            description: '再次进入时先呈现当前阶段、未完成任务和最近薄弱点，减少重复说明。',
            visual: pathPanel('从上次进度继续', [
              { label: '已完成', title: '函数基础', detail: '概念与图像理解', state: 'current' },
              { label: '未完成', title: '迁移练习', detail: '下次打开即可继续', state: 'next' },
              { label: '薄弱点', title: '解析式判断', detail: '需要再验证一次', state: 'past' },
            ]),
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
            visual: pathPanel('清楚的下一步', [
              { label: '动作 1', title: '继续讲解', detail: '补上当前概念缺口', state: 'current' },
              { label: '动作 2', title: '开始练习', detail: '用短题确认理解', state: 'next' },
              { label: '动作 3', title: '复习薄弱点', detail: '必要时回到基础', state: 'past' },
            ]),
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
            visual: boundaryPanel('学习陪伴边界', '解释与反馈', '提醒与规划', '不替代评价'),
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
