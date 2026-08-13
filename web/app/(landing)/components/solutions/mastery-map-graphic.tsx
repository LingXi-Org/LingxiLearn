import { FeatureGraphicShell } from '@/app/(landing)/enterprise/components/feature-graphics/feature-graphic-shell'

interface MasteryNode {
  id: string
  label: string
  value: string
  x: number
  y: number
  active?: boolean
}

const DEFAULT_NODES: readonly MasteryNode[] = [
  { id: 'concept', label: '函数概念', value: '86%', x: 16, y: 22 },
  { id: 'graph', label: '图像理解', value: '52%', x: 55, y: 18, active: true },
  { id: 'derivative', label: '导数基础', value: '38%', x: 76, y: 56 },
  { id: 'transfer', label: '迁移应用', value: '24%', x: 32, y: 68 },
]

interface MasteryMapGraphicProps {
  nodes?: readonly MasteryNode[]
}

/**
 * A compact knowledge-dependency map for the diagnosis page. The visual uses
 * the existing feature-tile shell and a small SVG graph so the new concept is
 * limited to the one relationship the existing graphics cannot express.
 */
export function MasteryMapGraphic({ nodes = DEFAULT_NODES }: MasteryMapGraphicProps = {}) {
  return (
    <FeatureGraphicShell>
      <div aria-hidden='true' className='absolute inset-0'>
        <svg
          aria-hidden='true'
          className='absolute inset-0 h-full w-full'
          fill='none'
          preserveAspectRatio='none'
          viewBox='0 0 420 260'
        >
          <path d='M82 72 C150 50 168 55 230 64' stroke='var(--border-1)' strokeWidth='1.5' />
          <path d='M230 64 C285 90 292 112 320 146' stroke='var(--border-1)' strokeWidth='1.5' />
          <path d='M82 178 C145 145 174 120 230 64' stroke='var(--border-1)' strokeWidth='1.5' />
          <path d='M82 178 C172 206 240 190 320 146' stroke='var(--border-1)' strokeWidth='1.5' />
        </svg>

        {nodes.map((node) => (
          <div
            key={node.id}
            className={`-translate-x-1/2 -translate-y-1/2 absolute w-[112px] rounded-xl border px-3 py-2 shadow-sm ${
              node.active
                ? 'border-[var(--text-primary)] bg-[var(--text-primary)] text-[var(--text-inverse)] motion-safe:animate-pulse'
                : 'border-[var(--border-1)] bg-[var(--white)] text-[var(--text-primary)]'
            }`}
            style={{ left: `${node.x}%`, top: `${node.y}%` }}
          >
            <span className='block truncate text-caption'>{node.label}</span>
            <span className='mt-1 block font-mono text-small'>{node.value}</span>
          </div>
        ))}
      </div>
    </FeatureGraphicShell>
  )
}
