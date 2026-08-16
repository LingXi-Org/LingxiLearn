import type { NavMenu } from '@/app/(landing)/components/navbar/components/nav-menu-chip/types'

export const LEARNING_EXPERIENCE_MENU: NavMenu = {
  label: '学习体验',
  items: [
    {
      title: '个性化学习',
      description: '动态规划属于你的学习路径',
      href: '/learning/personalized',
    },
    {
      title: '疑难讲解',
      description: '把抽象知识变成可交互讲解',
      href: '/learning/explanation',
    },
    {
      title: '作业辅导',
      description: '提示、分析，而非代替思考',
      href: '/learning/homework',
    },
    {
      title: '自适应练习',
      description: '根据掌握度动态生成训练',
      href: '/learning/practice',
    },
    {
      title: '学情诊断',
      description: '发现知识薄弱点与关联',
      href: '/learning/diagnosis',
    },
    {
      title: '学习陪伴',
      description: '持续理解你的学习状态',
      href: '/learning/companion',
    },
  ],
}

export const TEACHING_LOOP_MENU: NavMenu = {
  label: '教学闭环',
  items: [
    {
      title: '从问题到掌握',
      description: '诊断 → 讲解 → 练习 → 验证',
      href: '/learning',
    },
    {
      title: '个性化路径',
      description: '根据学习状态动态选择下一步',
      href: '/learning/personalized',
    },
    {
      title: '理解与诊断',
      description: '识别意图、基础与薄弱点',
      href: '/learning/diagnosis',
    },
    {
      title: '启发式讲解',
      description: '趣味引入 + 可视化 + 分步引导',
      href: '/learning/explanation',
    },
    {
      title: '练习与反馈',
      description: '针对性出题与错因反馈',
      href: '/learning/practice',
    },
    {
      title: '掌握验证',
      description: '同类题 / 迁移题 / 再评估',
      href: '/learning',
    },
  ],
}

export const SAFETY_OPENNESS_MENU: NavMenu = {
  label: '安全与开放',
  items: [
    {
      title: 'LingxiHarness',
      description: 'Skill-Native 运行时架构',
      href: '/safety/harness',
    },
    {
      title: '数据合规说明',
      description: '来源、授权、脱敏与边界',
      href: '/safety/data-compliance',
    },
    {
      title: '隐私政策',
      description: '学习数据与用户权利',
      href: '/privacy',
    },
    {
      title: '服务条款',
      description: '使用规则与教育边界',
      href: '/terms',
    },
    {
      title: 'LingxiSkills ↗',
      description: '能力注册表与文档库',
      href: 'https://skills.lingxilearn.cn/',
      external: true,
    },
    {
      title: 'LingxiGraph 文档 ↗',
      description: 'Agent Graph Runtime 开发文档',
      href: 'https://docs.lingxilearn.cn/docs/zh/',
      external: true,
    },
  ],
}

export const NAV_MENUS = [
  LEARNING_EXPERIENCE_MENU,
  TEACHING_LOOP_MENU,
  SAFETY_OPENNESS_MENU,
] as const

// Backward-compatible exports for other landing components importing the old names.
export const PLATFORM_MENU = LEARNING_EXPERIENCE_MENU
export const SOLUTIONS_MENU = TEACHING_LOOP_MENU
