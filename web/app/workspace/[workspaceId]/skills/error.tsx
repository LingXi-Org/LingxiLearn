'use client'

import { type ErrorBoundaryProps, ErrorState } from '@/app/workspace/[workspaceId]/components'

export default function SkillsError({ error, reset }: ErrorBoundaryProps) {
  return (
    <ErrorState
      error={error}
      reset={reset}
      title='技能加载失败'
      description='加载技能时出现问题，请稍后重试。'
      loggerName='SkillsError'
    />
  )
}
