import { cn } from '@/components/ui-kit'

export type LearningSignalKind = 'path' | 'dialogue' | 'evidence'

interface LearningSignalGraphicProps {
  kind: LearningSignalKind
}

const SIGNALS: Record<LearningSignalKind, { eyebrow: string; title: string; rows: string[] }> = {
  path: {
    eyebrow: '下一步学习动作',
    title: '根据当前状态继续',
    rows: ['复习函数图像', '完成一次迁移练习', '检查是否真正理解'],
  },
  dialogue: {
    eyebrow: '当前理解',
    title: '从你的问题继续',
    rows: ['定位卡住的位置', '换一种方式解释', '用自己的话复述'],
  },
  evidence: {
    eyebrow: '学习证据',
    title: '让判断有迹可循',
    rows: ['近期练习表现', '重复出现的错误', '下一步验证任务'],
  },
}

export function LearningSignalGraphic({ kind }: LearningSignalGraphicProps) {
  const signal = SIGNALS[kind]

  return (
    <div
      aria-hidden='true'
      className='flex h-full min-h-[240px] w-full flex-col justify-between rounded-lg border border-[var(--border-1)] bg-[var(--surface-1)] p-5 text-left shadow-[var(--shadow-card)] max-sm:p-4'
    >
      <div className='flex items-start justify-between gap-4'>
        <div className='min-w-0'>
          <p className='text-[11px] text-[var(--text-muted)] leading-[1.4]'>{signal.eyebrow}</p>
          <p className='mt-2 text-[16px] text-[var(--text-primary)] leading-[1.3]'>
            {signal.title}
          </p>
        </div>
        <span className='mt-0.5 h-2 w-2 shrink-0 rounded-full bg-[var(--brand)]' />
      </div>

      <div className='mt-6 flex flex-col gap-2'>
        {signal.rows.map((row, index) => (
          <div
            className='flex items-center gap-3 rounded-md border border-[var(--border-1)] bg-[var(--surface-2)] px-3 py-2.5'
            key={row}
          >
            <span
              className={cn(
                'flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px]',
                index === 0
                  ? 'bg-[var(--brand)] text-[var(--text-inverse)]'
                  : 'bg-[var(--surface-4)] text-[var(--text-muted)]'
              )}
            >
              {index + 1}
            </span>
            <span className='min-w-0 truncate text-[12px] text-[var(--text-secondary)]'>{row}</span>
          </div>
        ))}
      </div>

      <div className='mt-5 flex items-center gap-2 text-[11px] text-[var(--text-muted)]'>
        <span className='h-px flex-1 bg-[var(--border-1)]' />
        <span>LingXi 学习状态</span>
      </div>
    </div>
  )
}
