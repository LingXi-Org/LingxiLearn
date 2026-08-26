'use client'

import type { ComponentProps, RefObject } from 'react'
import { ChatSurfaceProvider, MothershipChat, UserInput } from './components'

interface ChatFeatureProps {
  showEmptyState: boolean
  greeting: string
  inputContainerRef: RefObject<HTMLDivElement | null>
  surfaceProps: Omit<ComponentProps<typeof ChatSurfaceProvider>, 'children'>
  inputProps: ComponentProps<typeof UserInput>
  transcriptProps: ComponentProps<typeof MothershipChat>
}

/** Presentation boundary for the empty composer and an active chat transcript. */
export function ChatFeature({
  showEmptyState,
  greeting,
  inputContainerRef,
  surfaceProps,
  inputProps,
  transcriptProps,
}: ChatFeatureProps) {
  return (
    <div className='relative flex h-full min-w-0 flex-1 flex-col'>
      {showEmptyState ? (
        <div className='h-full overflow-y-auto [scrollbar-gutter:stable_both-edges]'>
          <div className='flex min-h-full flex-col items-center justify-center px-6 pt-[2vh] pb-[22vh]'>
            <h1 className='mb-7 max-w-chat text-balance font-season text-[26px] text-[var(--text-primary)] leading-[1.15] tracking-[-0.01em] sm:text-[28px]'>
              {greeting}
            </h1>
            <div ref={inputContainerRef} className='relative w-full max-w-chat'>
              <ChatSurfaceProvider {...surfaceProps}>
                <UserInput {...inputProps} />
              </ChatSurfaceProvider>
            </div>
          </div>
        </div>
      ) : (
        <MothershipChat {...transcriptProps} />
      )}
    </div>
  )
}
