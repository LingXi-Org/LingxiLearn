'use client'

import { useEffect } from 'react'
import { useParams } from 'next/navigation'
import type { ProviderName } from '@/lib/api/contracts/providers'
import { createLogger } from '@/lib/logger'
import { setActiveProviderWorkspaceId, useProviderModels } from '@/hooks/queries/providers'

const logger = createLogger('ProviderModelsLoader')

function useLoadProvider(provider: ProviderName, workspaceId?: string) {
  const { error } = useProviderModels(provider, workspaceId)

  useEffect(() => {
    if (error) {
      logger.error(`Failed to load ${provider} models`, error)
    }
  }, [provider, error])
}

export function ProviderModelsLoader() {
  const params = useParams()
  const workspaceId = params?.workspaceId as string | undefined

  setActiveProviderWorkspaceId(workspaceId)
  useEffect(() => () => setActiveProviderWorkspaceId(undefined), [])

  useLoadProvider('base')
  useLoadProvider('ollama')
  useLoadProvider('ollama-cloud', workspaceId)
  useLoadProvider('vllm')
  useLoadProvider('litellm')
  useLoadProvider('openrouter')
  useLoadProvider('fireworks', workspaceId)
  useLoadProvider('together', workspaceId)
  useLoadProvider('baseten', workspaceId)
  return null
}
