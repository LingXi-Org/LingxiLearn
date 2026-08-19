import { notFound } from 'next/navigation'
import { LingxiDebugClient } from './lingxi-debug-client'

export default function LingxiDebugPage() {
  if (
    process.env.NODE_ENV !== 'development' ||
    process.env.LINGXILEARN_RUNTIME_DEBUG_ENABLED !== 'true'
  ) {
    notFound()
  }

  return <LingxiDebugClient />
}
