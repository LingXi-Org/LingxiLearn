'use client'

import type { ReactNode } from 'react'

/** Read-only compatibility surface for log/table consumers. The editable
 * workflow preview was intentionally removed; logs expose an audit summary. */
export function Preview({ className, height, width, children }: {
  className?: string
  height?: string | number
  width?: string | number
  children?: ReactNode
  [key: string]: unknown
}) {
  return (
    <div className={className} style={{ height, width }}>
      {children ?? <div className='p-4 text-sm text-[var(--text-muted)]'>只读执行快照</div>}
    </div>
  )
}

export function PreviewWorkflow(props: Record<string, unknown>) {
  return <Preview {...props} />
}
