import {
  AgentIcon,
  AnthropicIcon,
  GmailIcon,
  LinearIcon,
  SlackIcon,
  TableIcon,
} from '@/components/icons'
import type { BlockDef } from '@/app/(landing)/components/hero/components/hero-visual/workflow-data'

/**
 * Design-space geometry for the Build card's workflow showcase - a
 * support-triage pipeline flowing LEFT TO RIGHT: two triggers (a Gmail inbox
 * and a Slack channel) converge on a triage agent, which fans out to four
 * destinations - Linear, an eng escalation, a customer reply, and Tables.
 * Rows carry concrete values (not placeholders) so the canvas reads like a
 * configured workflow.
 *
 * Column geometry: three columns at x=0 / x=370 / x=740 on a 990-wide canvas.
 * The triggers straddle the agent's row; the four outputs stack down the
 * right column, spanning y=20-666 on a 686-tall canvas. The bounding box
 * exactly hugs the blocks, so the stage's flex-centering shows the whole
 * flow clean and uncut. Edges run from right handles to left handles at
 * `HANDLE_Y_OFFSET`, matching the real editor's horizontal layout.
 *
 * Icon tiles follow the platform rule: grey text-ramp tiles for first-party
 * blocks, brand colors only for REAL third-party marks, and white bordered
 * tiles for marks that carry their own colors.
 */
export const SHOWCASE_BLOCKS: BlockDef[] = [
  {
    id: 'gmail-trigger',
    name: '新支持邮件',
    icon: GmailIcon,
    bgColor: '#FFFFFF',
    tileBorder: true,
    isTrigger: true,
    rows: [
      { title: '发件人', value: '客户' },
      { title: '筛选', value: '未读' },
    ],
    x: 0,
    y: 150,
  },
  {
    id: 'slack-trigger',
    name: '新的 #support 帖子',
    icon: SlackIcon,
    bgColor: '#611F69',
    isTrigger: true,
    rows: [
      { title: '频道', value: '#support' },
      { title: '事件', value: '新消息' },
    ],
    x: 0,
    y: 424,
  },
  {
    id: 'triage',
    name: '分流请求',
    icon: AgentIcon,
    bgColor: 'var(--text-primary)',
    rows: [
      { title: '模型', value: 'Claude', valueIcon: AnthropicIcon },
      { title: '知识', value: '帮助中心' },
      { title: '指令', value: '分流 + 起草' },
    ],
    x: 370,
    y: 277,
  },
  {
    id: 'linear',
    name: '提交缺陷',
    icon: LinearIcon,
    bgColor: '#FFFFFF',
    tileBorder: true,
    isTerminal: true,
    rows: [
      { title: '团队', value: '平台' },
      { title: '优先级', value: '来自分流' },
    ],
    x: 740,
    y: 20,
  },
  {
    id: 'escalate',
    name: '升级给工程团队',
    icon: SlackIcon,
    bgColor: '#611F69',
    isTerminal: true,
    rows: [
      { title: '频道', value: '#eng-oncall' },
      { title: '条件', value: '紧急' },
    ],
    x: 740,
    y: 200,
  },
  {
    id: 'reply',
    name: '发送回复',
    icon: GmailIcon,
    bgColor: '#FFFFFF',
    tileBorder: true,
    isTerminal: true,
    rows: [
      { title: '收件人', value: '客户' },
      { title: '语气', value: '友好' },
    ],
    x: 740,
    y: 380,
  },
  {
    id: 'tables',
    name: '记录工单',
    icon: TableIcon,
    bgColor: 'var(--text-body)',
    isTerminal: true,
    rows: [
      { title: '数据表', value: '工单' },
      { title: '操作', value: '插入' },
    ],
    x: 740,
    y: 560,
  },
]

/** Source → target pairs; every edge is drawn (the flow renders finished). */
export const SHOWCASE_EDGES: ReadonlyArray<readonly [string, string]> = [
  ['gmail-trigger', 'triage'],
  ['slack-trigger', 'triage'],
  ['triage', 'linear'],
  ['triage', 'escalate'],
  ['triage', 'reply'],
  ['triage', 'tables'],
]

/** Design-space bounding box of the layout above. */
export const SHOWCASE_CANVAS = { width: 990, height: 686 } as const
