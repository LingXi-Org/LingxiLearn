import type { HeroWorkflowDefinition } from '@/app/(landing)/components/hero/components/hero-platform-loop'

/** A compact two-node flow for an undergraduate planning request. */
export const PERSONALIZED_HERO_WORKFLOW: HeroWorkflowDefinition = {
  blocks: [
    {
      id: 'university-goal',
      name: '大学课程目标',
      icon: 'start',
      bgColor: 'var(--text-muted)',
      isTrigger: true,
      rows: [
        { title: '方向', value: '线性代数期末' },
        { title: '卡点', value: '特征值计算' },
      ],
      x: 155,
      y: 50,
    },
    {
      id: 'adaptive-path',
      name: '生成复习路径',
      icon: 'brain',
      bgColor: 'var(--text-primary)',
      isTerminal: true,
      rows: [
        { title: '顺序', value: '概念 → 例题' },
        { title: '节奏', value: '按掌握状态' },
      ],
      x: 155,
      y: 260,
    },
  ],
  edges: [['university-goal', 'adaptive-path']],
  canvas: { width: 560, height: 430 },
}

/** A three-node research-methods flow for a graduate student. */
export const HOMEWORK_HERO_WORKFLOW: HeroWorkflowDefinition = {
  blocks: [
    {
      id: 'graduate-question',
      name: '研究生论文问题',
      icon: 'start',
      bgColor: 'var(--text-muted)',
      isTrigger: true,
      rows: [
        { title: '方法', value: '方差分析' },
        { title: '卡点', value: '结果解释' },
      ],
      x: 155,
      y: 34,
    },
    {
      id: 'result-interpretation',
      name: '拆解统计结果',
      icon: 'agent',
      bgColor: 'var(--text-primary)',
      rows: [
        { title: '指标', value: 'p 值与效应量' },
        { title: '方式', value: '对照论文语境' },
      ],
      x: 155,
      y: 208,
    },
    {
      id: 'research-check',
      name: '验证迁移理解',
      icon: 'chart',
      bgColor: 'var(--text-secondary)',
      isTerminal: true,
      rows: [
        { title: '形式', value: '改写结果段落' },
        { title: '反馈', value: '保留推理依据' },
      ],
      x: 155,
      y: 382,
    },
  ],
  edges: [
    ['graduate-question', 'result-interpretation'],
    ['result-interpretation', 'research-check'],
  ],
  canvas: { width: 560, height: 555 },
}

/** A deliberately short two-node flow for an adult career-learning request. */
export const PRACTICE_HERO_WORKFLOW: HeroWorkflowDefinition = {
  blocks: [
    {
      id: 'career-goal',
      name: '社会人学习目标',
      icon: 'start',
      bgColor: 'var(--text-muted)',
      isTrigger: true,
      rows: [
        { title: '方向', value: '数据分析转型' },
        { title: '主题', value: 'SQL 窗口函数' },
      ],
      x: 155,
      y: 70,
    },
    {
      id: 'transfer-practice',
      name: '安排迁移练习',
      icon: 'brain',
      bgColor: 'var(--text-primary)',
      isTerminal: true,
      rows: [
        { title: '难度', value: '贴近真实业务' },
        { title: '节奏', value: '利用碎片时间' },
      ],
      x: 155,
      y: 280,
    },
  ],
  edges: [['career-goal', 'transfer-practice']],
  canvas: { width: 560, height: 450 },
}

/** The four-stage teaching loop shown on the /learning overview page. */
export const LOOP_HERO_WORKFLOW: HeroWorkflowDefinition = {
  blocks: [
    {
      id: 'student-problem',
      name: '真实学习问题',
      icon: 'start',
      bgColor: 'var(--text-muted)',
      isTrigger: true,
      rows: [
        { title: '主题', value: '函数与导数复习' },
        { title: '期限', value: '下周单元测验' },
      ],
      x: 155,
      y: 34,
    },
    {
      id: 'loop-diagnose',
      name: '定位与学情诊断',
      icon: 'brain',
      bgColor: 'var(--text-secondary)',
      rows: [
        { title: '输入', value: '练习与测试记录' },
        { title: '输出', value: '薄弱点与先修关系' },
      ],
      x: 155,
      y: 208,
    },
    {
      id: 'loop-teach',
      name: '讲解与自适应练习',
      icon: 'agent',
      bgColor: 'var(--text-primary)',
      rows: [
        { title: '动作', value: '按掌握状态选择' },
        { title: '反馈', value: '每次作答即时更新' },
      ],
      x: 155,
      y: 382,
    },
    {
      id: 'loop-verify',
      name: '掌握验证与再评估',
      icon: 'chart',
      bgColor: 'var(--text-primary)',
      isTerminal: true,
      rows: [
        { title: '形式', value: '同类题 + 迁移题' },
        { title: '结果', value: '通过后进入下一阶段' },
      ],
      x: 155,
      y: 556,
    },
  ],
  edges: [
    ['student-problem', 'loop-diagnose'],
    ['loop-diagnose', 'loop-teach'],
    ['loop-teach', 'loop-verify'],
  ],
  canvas: { width: 560, height: 720 },
}

/** A three-node resume flow for a working learner returning to a prior topic. */
export const COMPANION_HERO_WORKFLOW: HeroWorkflowDefinition = {
  blocks: [
    {
      id: 'resume-progress',
      name: '恢复上次进度',
      icon: 'start',
      bgColor: 'var(--text-muted)',
      isTrigger: true,
      rows: [
        { title: '场景', value: '产品工作中的 A/B 测试' },
        { title: '进度', value: '置信区间未完成' },
      ],
      x: 155,
      y: 34,
    },
    {
      id: 'weak-point',
      name: '定位当前薄弱点',
      icon: 'brain',
      bgColor: 'var(--text-secondary)',
      rows: [
        { title: '知识', value: '抽样与不确定性' },
        { title: '状态', value: '需要复习' },
      ],
      x: 155,
      y: 208,
    },
    {
      id: 'next-task',
      name: '继续下一项任务',
      icon: 'chart',
      bgColor: 'var(--text-primary)',
      isTerminal: true,
      rows: [
        { title: '形式', value: '业务案例练习' },
        { title: '结果', value: '接续原计划' },
      ],
      x: 155,
      y: 382,
    },
  ],
  edges: [
    ['resume-progress', 'weak-point'],
    ['weak-point', 'next-task'],
  ],
  canvas: { width: 560, height: 555 },
}
