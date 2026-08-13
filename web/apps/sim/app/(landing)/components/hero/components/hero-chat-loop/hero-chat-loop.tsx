'use client'

import { useEffect, useState } from 'react'
import { cn, Tooltip } from '@sim/emcn'
import {
  ArrowRight,
  ArrowUp,
  Duplicate,
  Mic,
  Paperclip,
  Plus,
  Slash,
  ThumbsDown,
  ThumbsUp,
} from '@sim/emcn/icons'
import { ThinkingLoader } from '@/components/ui'
import { HERO_TOOLTIP_OFFSET } from '@/app/(landing)/components/hero/components/hero-platform-loop/sidebar-hotspots'

/** The conversation the loop plays - mirrors the seeded capture chat. */
const USER_MESSAGE = '有新线索注册时，补充公司数据并将其发布到 #sales。'
const REPLY_MESSAGE =
  '收到。我会构建一个工作流，为每个新注册线索补充公司信息、进行评分，并将摘要发布到 Slack 的 #sales 频道。'
const REPLY_WORDS = REPLY_MESSAGE.split(' ')
/** Word-reveal cadence for the streamed reply. */
const STREAM_WORD_MS = 55
/** Follow-up suggestions shown once the reply completes, like the real chat. */
const FOLLOW_UPS = ['用示例线索运行测试', '部署工作流', '添加线索评分标准'] as const

/** Where the chat pane is within one loop pass. */
export type HeroChatPhase = 'idle' | 'user' | 'thinking' | 'reply'

interface HeroChatLoopProps {
  /** Current phase, driven by the parent {@link HeroPlatformLoop} clock. */
  phase: HeroChatPhase
  /** True during the brief fade-out before the cycle restarts. */
  fading: boolean
}

/**
 * The Mothership chat pane of the hero's live layer - purely presentational;
 * the loop clock lives in `HeroPlatformLoop` so the chat and the workflow
 * stage animate off one timeline. Replays one exchange: the user message
 * slides in, the goo {@link ThinkingLoader} cycles while the Mothership
 * thinks, the reply lands with its action row.
 *
 * Visuals mirror the real chat pane (`--bg` column, grey user bubble, bare
 * reply text, the real composer chrome - 28px round icon buttons, mic + the
 * `#808080` send disc on the right cluster) so the seam with the surrounding
 * screenshot is invisible. The reply STREAMS in word by word (the way the
 * real Mothership streams its responses); once the text completes, the
 * "Suggested follow-ups" block (the real special-tags markup: numbered
 * `--border`-ruled rows with a trailing arrow) and the action row land
 * together; under `prefers-reduced-motion` it appears whole.
 * The content column is centered and capped (like the real full-width
 * MothershipChat) so it reads right both full-width (stage collapsed) and at
 * half width (stage open). Only the conversation fades on reset - the pane
 * and composer are persistent chrome.
 */
export function HeroChatLoop({ phase, fading }: HeroChatLoopProps) {
  const showUser = phase !== 'idle'
  const showThinking = phase === 'thinking'
  const showReply = phase === 'reply'
  const [revealedWords, setRevealedWords] = useState(0)

  // Stream the reply word by word while the phase holds on 'reply'; any other
  // phase (the next cycle's reset) rewinds it for the following pass. The
  // count derives from ELAPSED time, not tick count, so throttled background
  // tabs catch up in chunks instead of stalling mid-sentence.
  useEffect(() => {
    if (!showReply) {
      setRevealedWords(0)
      return
    }

    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    let interval: ReturnType<typeof setInterval> | null = null

    const stream = () => {
      const startedAt = performance.now()
      interval = setInterval(() => {
        const elapsed = performance.now() - startedAt
        const n = Math.min(Math.floor(elapsed / STREAM_WORD_MS) + 1, REPLY_WORDS.length)
        setRevealedWords(n)
        if (n >= REPLY_WORDS.length && interval) clearInterval(interval)
      }, STREAM_WORD_MS)
    }

    // Re-synced on 'change' (not just on mount) so toggling the preference
    // mid-stream - e.g. HeroPlatformLoop's showFinished setting phase to
    // 'reply' while it's already 'reply' - still snaps the reply to complete
    // instead of leaving it mid-word until the running interval catches up.
    const syncMotionPreference = () => {
      if (interval) clearInterval(interval)
      if (media.matches) {
        setRevealedWords(REPLY_WORDS.length)
        return
      }
      stream()
    }

    syncMotionPreference()
    media.addEventListener('change', syncMotionPreference)
    return () => {
      media.removeEventListener('change', syncMotionPreference)
      if (interval) clearInterval(interval)
    }
  }, [showReply])

  const replyComplete = revealedWords >= REPLY_WORDS.length

  return (
    <div className='flex h-full w-full flex-col bg-[var(--bg)]'>
      <div
        className={cn(
          'mx-auto flex min-h-0 w-full max-w-[640px] flex-1 flex-col gap-6 overflow-hidden px-6 pt-6 transition-opacity duration-300 ease-out',
          fading ? 'opacity-0' : 'opacity-100'
        )}
      >
        <div
          className={cn(
            'max-w-[82%] self-end rounded-2xl bg-[var(--surface-3)] px-4 py-3 text-[15px] text-[var(--text-primary)] leading-[1.5] transition-[opacity,transform] duration-200 ease-out',
            showUser ? 'translate-y-0 opacity-100' : 'translate-y-2 opacity-0'
          )}
        >
          {USER_MESSAGE}
        </div>

        {showThinking && (
          <ThinkingLoader size={26} phase locale='zh-CN' labelRatio={0.58} className='mt-1' />
        )}

        <div
          className={cn(
            'flex flex-col gap-4 transition-opacity duration-200 ease-out',
            showReply ? 'opacity-100' : 'opacity-0'
          )}
        >
          <p className='text-[15px] text-[var(--text-primary)] leading-[1.6]'>
            {REPLY_WORDS.slice(0, revealedWords).join(' ')}
          </p>
          <div
            className={cn(
              'flex flex-col gap-4 transition-opacity duration-200 ease-out',
              replyComplete ? 'opacity-100' : 'opacity-0'
            )}
          >
            <div className='flex flex-col'>
              <span className='text-[var(--text-body)] text-sm'>推荐后续操作</span>
              <div className='mt-1.5 flex flex-col'>
                {FOLLOW_UPS.map((title, i) => (
                  <span
                    key={title}
                    className={cn(
                      'flex items-center gap-2 border-[var(--border)] px-2 py-2 text-left',
                      i > 0 && 'border-t'
                    )}
                  >
                    <span className='flex size-[16px] flex-shrink-0 items-center justify-center'>
                      <span className='text-[var(--text-icon)] text-sm'>{i + 1}</span>
                    </span>
                    <span className='flex-1 text-[var(--text-body)] text-sm'>{title}</span>
                    <ArrowRight className='size-[16px] shrink-0 text-[var(--text-icon)]' />
                  </span>
                ))}
              </div>
            </div>
            <div className='flex items-center gap-3 text-[var(--text-icon)]'>
              <Duplicate className='size-[14px]' />
              <ThumbsUp className='size-[14px]' />
              <ThumbsDown className='size-[14px]' />
            </div>
          </div>
        </div>
      </div>

      <div className='pointer-events-auto mx-auto mb-5 w-[calc(100%-40px)] max-w-[600px] shrink-0 rounded-2xl border border-[var(--border-1)] bg-[var(--white)] px-2.5 py-2'>
        <p className='px-1.5 pt-1 text-[15px] text-[var(--text-muted)]'>向 Sim 发送消息</p>
        <div className='mt-2 flex items-center gap-1.5'>
          <Tooltip.Root>
            <Tooltip.Trigger asChild>
              <span
                className='flex size-[28px] items-center justify-center rounded-full transition-colors hover-hover:bg-[var(--surface-hover)]'
                aria-label='添加资源'
              >
                <Plus className='size-[16px] text-[var(--text-icon)]' />
              </span>
            </Tooltip.Trigger>
            <Tooltip.Content offset={HERO_TOOLTIP_OFFSET}>添加资源</Tooltip.Content>
          </Tooltip.Root>
          <Tooltip.Root>
            <Tooltip.Trigger asChild>
              <span
                className='flex size-[28px] items-center justify-center rounded-full transition-colors hover-hover:bg-[var(--surface-hover)]'
                aria-label='附加文件'
              >
                <Paperclip className='size-[16px] text-[var(--text-icon)]' />
              </span>
            </Tooltip.Trigger>
            <Tooltip.Content offset={HERO_TOOLTIP_OFFSET}>附加文件</Tooltip.Content>
          </Tooltip.Root>
          <Tooltip.Root>
            <Tooltip.Trigger asChild>
              <span
                className='flex size-[28px] items-center justify-center rounded-full transition-colors hover-hover:bg-[var(--surface-hover)]'
                aria-label='技能'
              >
                <Slash className='size-[16px] text-[var(--text-icon)]' />
              </span>
            </Tooltip.Trigger>
            <Tooltip.Content offset={HERO_TOOLTIP_OFFSET}>技能</Tooltip.Content>
          </Tooltip.Root>
          <span className='ml-auto flex items-center gap-1.5'>
            <Tooltip.Root>
              <Tooltip.Trigger asChild>
                <span
                  className='flex size-[28px] items-center justify-center rounded-full transition-colors hover-hover:bg-[var(--surface-hover)]'
                  aria-label='语音输入'
                >
                  <Mic className='size-[16px] text-[var(--text-icon)]' />
                </span>
              </Tooltip.Trigger>
              <Tooltip.Content offset={HERO_TOOLTIP_OFFSET}>语音输入</Tooltip.Content>
            </Tooltip.Root>
            <span className='flex size-[28px] items-center justify-center rounded-full bg-[#808080]'>
              <ArrowUp className='size-[16px] text-white' />
            </span>
          </span>
        </div>
      </div>
    </div>
  )
}
