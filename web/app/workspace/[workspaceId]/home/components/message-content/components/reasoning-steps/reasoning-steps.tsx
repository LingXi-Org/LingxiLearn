'use client'

import { useState } from 'react'
import { ChevronDown, cn, Expandable, ExpandableContent } from '@sim/emcn'
import { ShimmerText } from '@/components/ui'
import type { ReasoningStep, ReasoningStepStatus } from '../../../../types'

interface ReasoningStepsProps {
  steps: ReasoningStep[]
  isStreaming?: boolean
}

function statusDotClass(status: ReasoningStepStatus): string {
  switch (status) {
    case 'complete':
      return 'bg-[var(--text-icon)]'
    case 'error':
      return 'bg-[var(--text-error)]'
    case 'active':
      return 'animate-pulse bg-[var(--text-brand)]'
    default:
      return 'bg-[var(--text-muted)]'
  }
}

/**
 * Sim's compact, collapsible plan lane. The component intentionally
 * accepts summaries rather than arbitrary model text: LingxiGraph's adapter
 * is responsible for producing the safe phase descriptions.
 */
export function ReasoningSteps({ steps, isStreaming = false }: ReasoningStepsProps) {
  const [manualExpanded, setManualExpanded] = useState<boolean | null>(null)
  if (steps.length === 0) return null

  const hasActiveStep = steps.some((step) => step.status === 'active' || step.status === 'pending')
  const expanded = manualExpanded ?? (isStreaming && hasActiveStep)
  const latest = steps[steps.length - 1]

  return (
    <div className='flex flex-col gap-1.5'>
      <button
        type='button'
        onClick={() => setManualExpanded(!expanded)}
        aria-expanded={expanded}
        className='group/reasoning flex cursor-pointer items-center gap-2 text-left'
      >
        <div className='flex size-[16px] flex-shrink-0 items-center justify-center'>
          <span
            aria-hidden='true'
            className={cn('size-[6px] rounded-full', statusDotClass(latest.status))}
          />
        </div>
        {hasActiveStep && isStreaming ? (
          <ShimmerText className='text-sm'>执行计划</ShimmerText>
        ) : (
          <span className='text-[var(--text-body)] text-sm'>执行计划</span>
        )}
        <ChevronDown
          className={cn(
            'size-[14px] text-[var(--text-icon)] opacity-0 transition-[transform,opacity] duration-150 group-hover/reasoning:opacity-100 group-focus-visible/reasoning:opacity-100',
            !expanded && '-rotate-90'
          )}
        />
      </button>
      <Expandable expanded={expanded}>
        <ExpandableContent>
          <div className='flex flex-col gap-2 py-0.5 pl-6'>
            {steps.map((step) => (
              <div key={step.id} className='flex gap-2 text-[13px] leading-[18px]'>
                <span
                  aria-hidden='true'
                  className={cn(
                    'mt-[6px] size-[5px] flex-shrink-0 rounded-full',
                    statusDotClass(step.status)
                  )}
                />
                <div className='min-w-0'>
                  <div className='text-[var(--text-body)]'>{step.title}</div>
                  <div className='text-[var(--text-muted)]'>{step.summary}</div>
                </div>
              </div>
            ))}
          </div>
        </ExpandableContent>
      </Expandable>
    </div>
  )
}
