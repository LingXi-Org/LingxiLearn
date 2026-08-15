import { AgentIcon, BrainIcon, ChartBarIcon, StartIcon, TableIcon } from '@/components/icons'
import type { BlockDef } from '@/app/(landing)/components/hero/components/hero-visual/workflow-data'
import { BLOCK_WIDTH } from '@/app/(landing)/components/hero/components/hero-visual/workflow-data'

/**
 * Design-space geometry for the hero's live workflow stage - the adaptive
 * learning flow the chat conversation "builds": Start feeds the learner-state
 * agent, then branches into explanation, practice, and review. Block tiles use
 * the platform's existing grey text ramp and icon treatment.
 *
 * Blocks are ordered by build sequence - the stage reveals `blocks[0..built-1]`
 * as the loop's build counter advances, and an edge draws once both its
 * endpoints are on canvas.
 */
export const STAGE_BLOCKS: BlockDef[] = [
  {
    id: 'start',
    name: '开始学习',
    icon: StartIcon,
    bgColor: 'var(--text-muted)',
    isTrigger: true,
    rows: [{ title: '输入', value: '-' }],
    x: 155,
    y: 12,
  },
  {
    id: 'enrich',
    name: '分析学习状态',
    icon: AgentIcon,
    bgColor: 'var(--text-primary)',
    rows: [
      { title: '目标', value: '-' },
      { title: '掌握度', value: '-' },
      { title: '薄弱点', value: '-' },
    ],
    x: 155,
    y: 172,
  },
  {
    id: 'score',
    name: '个性化讲解',
    icon: BrainIcon,
    bgColor: 'var(--text-secondary)',
    rows: [
      { title: '方式', value: '图解 + 对话' },
      { title: '重点', value: '-' },
    ],
    x: 155,
    y: 390,
  },
  {
    id: 'practice',
    name: '针对性练习',
    icon: ChartBarIcon,
    bgColor: '#611F69',
    isTerminal: true,
    rows: [
      { title: '难度', value: '-' },
      { title: '题目', value: '-' },
    ],
    x: 0,
    y: 580,
  },
  {
    id: 'review',
    name: '生成复习建议',
    icon: TableIcon,
    bgColor: 'var(--text-body)',
    isTerminal: true,
    rows: [
      { title: '薄弱点', value: '-' },
      { title: '下一步', value: '-' },
    ],
    x: 310,
    y: 580,
  },
]

/** Source → target pairs, drawn in order as their endpoints land on canvas. */
export const STAGE_EDGES: ReadonlyArray<readonly [string, string]> = [
  ['start', 'enrich'],
  ['enrich', 'score'],
  ['score', 'practice'],
  ['score', 'review'],
]

/** Design-space bounding box of the layout above. */
export const STAGE_CANVAS = { width: 560, height: 700 } as const

/**
 * Approximate rendered block height - the icon-tile header (~40px) plus the
 * rows section (16px padding + 21px per row + 8px gaps). Used to place a
 * block's bottom (outgoing) handle; a few px of drift is invisible at stage
 * scale.
 */
export function blockHeight(block: BlockDef): number {
  const n = block.rows.length
  return 40 + (n > 0 ? 16 + n * 21 + (n - 1) * 8 : 0)
}

/**
 * Rounded orthogonal ("smoothstep") path for a VERTICAL flow - from a source's
 * bottom-center handle to a target's top-center handle, stepping at the
 * vertical midpoint with `r`-radius corners. The horizontal-flow counterpart
 * lives in `hero-visual/workflow-data.ts`.
 */
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

/** Handle anchor points for a block at its fixed position. */
export function handleAnchors(block: BlockDef) {
  return {
    out: { x: block.x + BLOCK_WIDTH / 2, y: block.y + blockHeight(block) },
    in: { x: block.x + BLOCK_WIDTH / 2, y: block.y },
  }
}
