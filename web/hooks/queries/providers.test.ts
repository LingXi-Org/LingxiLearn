/**
 * @vitest-environment node
 */
import { QueryClient } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'

const queryClient = vi.hoisted(() => ({ current: undefined as QueryClient | undefined }))

vi.mock('@/app/_shell/providers/get-query-client', () => ({
  getQueryClient: () => queryClient.current,
}))

import {
  getCachedProviderModelInfo,
  getCachedProviderModels,
  getActiveWorkspaceProviderModels,
  providerKeys,
  setActiveProviderWorkspaceId,
} from '@/hooks/queries/providers'

describe('provider model query cache reads', () => {
  afterEach(() => {
    queryClient.current?.clear()
    queryClient.current = undefined
    setActiveProviderWorkspaceId(undefined)
  })

  it('reads models and model metadata from the canonical query key', () => {
    queryClient.current = new QueryClient()
    queryClient.current.setQueryData(providerKeys.list('openrouter'), {
      models: ['openrouter/openai/gpt-5'],
      modelInfo: { 'openrouter/openai/gpt-5': { id: 'openrouter/openai/gpt-5' } },
    })

    expect(getCachedProviderModels('openrouter')).toEqual(['openrouter/openai/gpt-5'])
    expect(getCachedProviderModelInfo('openrouter')).toEqual({
      'openrouter/openai/gpt-5': { id: 'openrouter/openai/gpt-5' },
    })
  })

  it('keeps workspace-scoped provider entries isolated', () => {
    queryClient.current = new QueryClient()
    queryClient.current.setQueryData(providerKeys.list('fireworks', 'workspace-a'), {
      models: ['model-a'],
    })
    queryClient.current.setQueryData(providerKeys.list('fireworks', 'workspace-b'), {
      models: ['model-b'],
    })

    expect(getCachedProviderModels('fireworks', 'workspace-a')).toEqual(['model-a'])
    expect(getCachedProviderModels('fireworks', 'workspace-b')).toEqual(['model-b'])
    expect(getCachedProviderModels('fireworks')).toEqual([])
  })

  it('reads only the explicitly active workspace for context-free consumers', () => {
    queryClient.current = new QueryClient()
    queryClient.current.setQueryData(
      providerKeys.list('together', 'workspace-a'),
      { models: ['older'] },
      { updatedAt: 1 }
    )
    queryClient.current.setQueryData(
      providerKeys.list('together', 'workspace-b'),
      { models: ['newer'] },
      { updatedAt: 2 }
    )

    setActiveProviderWorkspaceId('workspace-a')
    expect(getActiveWorkspaceProviderModels('together')).toEqual(['older'])

    setActiveProviderWorkspaceId('workspace-c')
    expect(getActiveWorkspaceProviderModels('together')).toEqual([])
  })
})
