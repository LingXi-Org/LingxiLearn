'use client'

import { memo, useEffect, useRef, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { Check, cn, Duplicate, Split, Tooltip, toast } from '@/components/ui-kit'
import { forkAgentTask } from '@/lib/api/domains/agent-tasks'
import { useFolderStore } from '@/stores/folders/store'

const SPECIAL_TAGS = 'thinking|options|usage_upgrade|credential|mothership-error|file|question'

function toPlainText(raw: string): string {
  return (
    raw
      // Strip special tags and their contents
      .replace(new RegExp(`<\\/?(${SPECIAL_TAGS})(?:>[\\s\\S]*?<\\/(${SPECIAL_TAGS})>|>)`, 'g'), '')
      // Strip markdown
      .replace(/^#{1,6}\s+/gm, '')
      .replace(/\*\*(.+?)\*\*/g, '$1')
      .replace(/\*(.+?)\*/g, '$1')
      .replace(/`{3}[\s\S]*?`{3}/g, '')
      .replace(/`(.+?)`/g, '$1')
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
      .replace(/^[>\-*]\s+/gm, '')
      .replace(/!\[[^\]]*\]\([^)]+\)/g, '')
      // Normalize whitespace
      .replace(/\n{3,}/g, '\n\n')
      .trim()
  )
}

const ICON_CLASS = 'size-[14px]'
const BUTTON_CLASS =
  'flex size-[26px] items-center justify-center rounded-[6px] text-[var(--text-icon)] transition-colors hover-hover:bg-[var(--surface-hover)] focus-visible:outline-none'

interface MessageActionsProps {
  content: string
  requestId?: string
}

export const MessageActions = memo(function MessageActions({
  content,
  requestId,
}: MessageActionsProps) {
  const router = useRouter()
  const params = useParams<{ workspaceId: string }>()
  const [copied, setCopied] = useState(false)
  const resetTimeoutRef = useRef<number | null>(null)
  const [isLingxiForking, setIsLingxiForking] = useState(false)

  useEffect(() => {
    return () => {
      if (resetTimeoutRef.current !== null) {
        window.clearTimeout(resetTimeoutRef.current)
      }
    }
  }, [])

  const copyToClipboard = async () => {
    if (!content) return
    const text = toPlainText(content)
    if (!text) return
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      if (resetTimeoutRef.current !== null) {
        window.clearTimeout(resetTimeoutRef.current)
      }
      resetTimeoutRef.current = window.setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard unavailable */
    }
  }

  const handleFork = async () => {
    if (!requestId || isLingxiForking) return
    setIsLingxiForking(true)
    try {
      const result = await forkAgentTask(requestId)
      useFolderStore.getState().clearChatSelection()
      router.push(`/workspace/${params.workspaceId}/chat/${result.id}`)
    } catch {
      toast.error('Failed to restart learning task')
    } finally {
      setIsLingxiForking(false)
    }
  }

  const hasContent = Boolean(content)
  const canFork = Boolean(requestId)
  const forkLabel = 'Restart from original prompt'
  if (!hasContent && !canFork) return null

  return (
    <div className='flex items-center gap-0.5'>
      {hasContent && (
        <Tooltip.Root>
          <Tooltip.Trigger asChild>
            <button
              type='button'
              aria-label='Copy message'
              onClick={copyToClipboard}
              className={BUTTON_CLASS}
            >
              {copied ? <Check className={ICON_CLASS} /> : <Duplicate className={ICON_CLASS} />}
            </button>
          </Tooltip.Trigger>
          <Tooltip.Content side='top'>{copied ? 'Copied message' : 'Copy message'}</Tooltip.Content>
        </Tooltip.Root>
      )}
      {canFork && (
        <Tooltip.Root>
          <Tooltip.Trigger asChild>
            <button
              type='button'
              aria-label={forkLabel}
              onClick={handleFork}
              disabled={isLingxiForking}
              className={cn(BUTTON_CLASS, isLingxiForking && 'cursor-not-allowed opacity-50')}
            >
              <Split className={cn(ICON_CLASS, 'rotate-90')} />
            </button>
          </Tooltip.Trigger>
          <Tooltip.Content side='top'>{forkLabel}</Tooltip.Content>
        </Tooltip.Root>
      )}
    </div>
  )
})
