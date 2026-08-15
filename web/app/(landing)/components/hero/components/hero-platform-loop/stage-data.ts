import { AgentIcon, BrainIcon, ChartBarIcon, StartIcon, TableIcon } from '@/components/icons'
import type { BlockDef } from '@/app/(landing)/components/hero/components/hero-visual/workflow-data'
import { BLOCK_WIDTH } from '@/app/(landing)/components/hero/components/hero-visual/workflow-data'

/** The learning loop rendered inside the homepage's existing workflow stage. */
export const STAGE_BLOCKS: BlockDef[] = [
  {
    id: 'goal',
    name: '你的目标',
    icon: StartIcon,
    bgColor: 'var(--text-muted)',
    isTrigger: true,
    rows: [{ title: '主题', value: '交叉熵为什么有效' }],
    x: 155,
    y: 10,
  },
  {
    id: 'topic',
    name: '理解「交叉熵为什么有效」',
    icon: BrainIcon,
    bgColor: 'var(--text-primary)',
    rows: [{ title: '主题', value: '交叉熵为什么有效' }],
    x: 155,
    y: 125,
  },
  {
    id: 'question',
    name: '理解你的问题',
    icon: AgentIcon,
    bgColor: 'var(--text-primary)',
    rows: [
      { title: '问题', value: '分类误差' },
      { title: '目标', value: '建立理解' },
    ],
    x: 155,
    y: 240,
  },
  {
    id: 'state',
    name: '检查当前掌握状态',
    icon: BrainIcon,
    bgColor: 'var(--text-secondary)',
    rows: [
      { title: '知识', value: '概率与信息量' },
      { title: '状态', value: '待确认' },
    ],
    x: 155,
    y: 355,
  },
  {
    id: 'prerequisite',
    name: '补充前置概念',
    icon: TableIcon,
    bgColor: 'var(--text-body)',
    rows: [
      { title: '内容', value: '概率与信息量' },
      { title: '方式', value: '讲解' },
    ],
    x: 0,
    y: 485,
  },
  {
    id: 'visual',
    name: '建立直观理解',
    icon: BrainIcon,
    bgColor: 'var(--text-body)',
    rows: [
      { title: '内容', value: '可视化解释' },
      { title: '方式', value: '图解' },
    ],
    x: 310,
    y: 485,
  },
  {
    id: 'check',
    name: '检验理解',
    icon: ChartBarIcon,
    bgColor: 'var(--text-secondary)',
    rows: [
      { title: '形式', value: '练习题' },
      { title: '反馈', value: '即时' },
    ],
    x: 155,
    y: 620,
  },
  {
    id: 'update',
    name: '更新学习状态',
    icon: AgentIcon,
    bgColor: 'var(--text-primary)',
    isTerminal: true,
    rows: [
      { title: '结果', value: '已记录' },
      { title: '下一步', value: '动态调整' },
    ],
    x: 155,
    y: 750,
  },
]

export const STAGE_EDGES: ReadonlyArray<readonly [string, string]> = [
  ['goal', 'topic'],
  ['topic', 'question'],
  ['question', 'state'],
  ['state', 'prerequisite'],
  ['state', 'visual'],
  ['prerequisite', 'check'],
  ['visual', 'check'],
  ['check', 'update'],
]

export const STAGE_CANVAS = { width: 560, height: 880 } as const

export function blockHeight(block: BlockDef): number {
  const n = block.rows.length
  return 40 + (n > 0 ? 16 + n * 21 + (n - 1) * 8 : 0)
}

export function verticalSmoothStep(sx: number, sy: number, tx: number, ty: number, r = 8): string {
  if (Math.abs(tx - sx) < 1) return `M ${sx} ${sy} L ${tx} ${ty}`
  const midY = (sy + ty) / 2
  const dir = tx >= sx ? 1 : -1
  return [
    `M ${sx} ${sy}`,
    `L ${sx} ${midY - r}`,
    `Q ${sx} ${midY} ${sx + dir * r} ${midY}`,
    `L ${tx - dir * r} ${midY}`,
    `Q ${tx} ${midY} ${tx} ${midY + r}`,
    `L ${tx} ${ty}`,
  ].join(' ')
}

export function handleAnchors(block: BlockDef) {
  return {
    out: { x: block.x + BLOCK_WIDTH / 2, y: block.y + blockHeight(block) },
    in: { x: block.x + BLOCK_WIDTH / 2, y: block.y },
  }
}
