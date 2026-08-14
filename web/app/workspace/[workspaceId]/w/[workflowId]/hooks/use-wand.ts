'use client'

import { useState } from 'react'

export function useWand({ currentValue, onStreamStart, onGeneratedContent }: any) {
  const [isLoading, setIsLoading] = useState(false)
  return {
    isLoading,
    isStreaming: false,
    generate: async () => {
      setIsLoading(true)
      onStreamStart?.()
      onGeneratedContent?.(currentValue)
      setIsLoading(false)
    },
  }
}
