'use client'

import { useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { LandingPromptStorage } from '@/lib/landing/browser-storage'

/**
 * Stores the typed prompt in browser storage and routes to the Lingxi workspace.
 * Shared by the landing
 * preview's chat pane and the home empty-state input.
 */
export function useLandingSubmit() {
  const router = useRouter()
  return useCallback(
    (text: string) => {
      const trimmed = text.trim()
      if (!trimmed) return
      LandingPromptStorage.store(trimmed)
      router.push('/workspace/lingxi/home/')
    },
    [router]
  )
}
