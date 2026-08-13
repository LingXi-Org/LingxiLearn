import type { NavMenu } from '@/app/(landing)/components/navbar/components/nav-menu-chip/types'

const LEARNING_HOME = '/workspace/lingxi/home'

export const LEARNING_EXPERIENCE_MENU: NavMenu = {
  label: '学习体验',
  items: [
    {
      title: '个性化学习',
      description: '动态规划属于你的学习路径',
      href: LEARNING_HOME,
    },
    {
      title: '疑难讲解',
      description: '把抽象知识变成可交互讲解',
      href: LEARNING_HOME,
    },
    {
      title: '作业辅导',
      description: '提示、分析，而非代替思考',
      href: LEARNING_HOME,
    },
    {
      title: '自适应练习',
      description: '根据掌握度动态生成训练',
      href: LEARNING_HOME,
    },
    {
      title: '学情诊断',
      description: '发现知识薄弱点与关联',
      href: LEARNING_HOME,
    },
    {
      title: '学习陪伴',
      description: '持续理解你的学习状态',
      href: LEARNING_HOME,
    },
  ],
}

export const TEACHING_LOOP_MENU: NavMenu = {
  label: '教学闭环',
  items: [
    {
      title: '从问题到掌握',
      description: '诊断 → 讲解 → 练习 → 验证',
      href: LEARNING_HOME,
    },
    {
      title: '个性化路径',
      description: '根据学习状态动态选择下一步',
      href: LEARNING_HOME,
    },
    {
      title: '理解与诊断',
      description: '识别意图、基础与薄弱点',
      href: LEARNING_HOME,
    },
    {
      title: '启发式讲解',
      description: '趣味引入 + 可视化 + 分步引导',
      href: LEARNING_HOME,
    },
    {
      title: '练习与反馈',
      description: '针对性出题与错因反馈',
      href: LEARNING_HOME,
    },
    {
      title: '掌握验证',
      description: '同类题 / 迁移题 / 再评估',
      href: LEARNING_HOME,
    },
  ],
}

export const AGENTS_MENU: NavMenu = {
  label: '智能体',
  items: [
    {
      title: '多智能体协作',
      description: '让不同 Agent 专注不同教学任务',
      href: '/workflows',
    },
    {
      title: '教学 Skills',
      description: '可组合、可复用的教育能力',
      href: '/workflows',
    },
    {
      title: '意图理解',
      description: '理解学生此刻真正需要什么',
      href: LEARNING_HOME,
    },
    {
      title: '工具与知识增强',
      description: 'Search / RAG / Tool Calling',
      href: '/knowledge',
    },
    {
      title: '学习记忆',
      description: '持续维护学情与上下文',
      href: '/knowledge',
    },
    {
      title: 'LingxiGraph ↗',
      description: 'Agent Graph Runtime',
      href: LEARNING_HOME,
    },
  ],
}

export const TECHNICAL_VALIDATION_MENU: NavMenu = {
  label: '技术验证',
  items: [
    {
      title: '系统架构',
      description: 'Agent / Model / Tool / Data',
      href: '/library',
    },
    {
      title: '运行证据',
      description: 'Trace / Log / Screenshot',
      href: '/logs',
    },
    {
      title: '评测结果',
      description: '质量、教学效果与系统指标',
      href: '/library',
    },
    {
      title: '数据与知识库',
      description: '来源、检索与更新方式',
      href: '/knowledge',
    },
    {
      title: '失败处理',
      description: '异常、低置信度与降级机制',
      href: '/logs',
    },
    {
      title: '部署与复现',
      description: 'README / Config / Test',
      href: '/library',
    },
  ],
}

export const SAFETY_OPENNESS_MENU: NavMenu = {
  label: '安全与开放',
  items: [
    {
      title: '学习数据隐私',
      description: '最小化、授权、脱敏与删除',
      href: '/privacy',
    },
    {
      title: '教育安全边界',
      description: 'AI 辅助教学，而非替代教师判断',
      href: '/terms',
    },
    {
      title: '结果可追溯',
      description: '来源、调用轨迹与生成依据',
      href: '/logs',
    },
    {
      title: '开源与复现',
      description: 'Code / Skills / Docs / Examples',
      href: 'https://github.com/simstudioai/sim',
      external: true,
    },
    {
      title: '第三方依赖',
      description: '模型、API、许可证与版本说明',
      href: '/library',
    },
    {
      title: '开放生态',
      description: 'LingxiGraph / Learn / Skills',
      href: 'https://github.com/simstudioai/sim',
      external: true,
    },
  ],
}

export const NAV_MENUS = [
  LEARNING_EXPERIENCE_MENU,
  TEACHING_LOOP_MENU,
  AGENTS_MENU,
  TECHNICAL_VALIDATION_MENU,
  SAFETY_OPENNESS_MENU,
] as const

// Backward-compatible exports for other landing components importing the old names.
export const PLATFORM_MENU = LEARNING_EXPERIENCE_MENU
export const RESOURCES_MENU = TECHNICAL_VALIDATION_MENU
export const SOLUTIONS_MENU = TEACHING_LOOP_MENU
