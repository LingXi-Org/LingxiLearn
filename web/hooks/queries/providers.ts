import { queryOptions, useQuery } from '@tanstack/react-query'
import { requestJson } from '@/lib/api/client/request'
import {
  getBaseProviderModelsContract,
  getBasetenProviderModelsContract,
  getFireworksProviderModelsContract,
  getLitellmProviderModelsContract,
  getOllamaCloudProviderModelsContract,
  getOllamaProviderModelsContract,
  getOpenRouterEmbeddingModelsContract,
  getOpenRouterProviderModelsContract,
  getTogetherProviderModelsContract,
  getVllmProviderModelsContract,
  type ProviderModelsResponse,
  type ProviderName,
} from '@/lib/api/contracts/providers'
import { createLogger } from '@/lib/logger'
import { getErrorMessage } from '@/lib/utils/errors'
import { getQueryClient } from '@/app/_shell/providers/get-query-client'

export type ProviderModelSource = ProviderName | 'openrouter-embeddings'

const logger = createLogger('ProviderModelsQuery')

export const PROVIDER_MODELS_STALE_TIME = 5 * 60 * 1000

export const providerKeys = {
  all: ['provider-models'] as const,
  lists: () => [...providerKeys.all, 'list'] as const,
  list: (provider: string, workspaceId?: string) =>
    [...providerKeys.lists(), provider, workspaceId ?? ''] as const,
}

async function fetchProviderModels(
  provider: ProviderModelSource,
  signal?: AbortSignal,
  workspaceId?: string
): Promise<ProviderModelsResponse> {
  try {
    const data = await requestProviderModels(provider, signal, workspaceId)
    const models: string[] = Array.isArray(data.models) ? data.models : []
    const uniqueModels = provider.startsWith('openrouter') ? Array.from(new Set(models)) : models

    return {
      models: uniqueModels,
      modelInfo: data.modelInfo,
    }
  } catch (error) {
    logger.warn(`Failed to fetch ${provider} models`, {
      error: getErrorMessage(error, 'Unknown error'),
    })
    throw error
  }
}

async function requestProviderModels(
  provider: ProviderModelSource,
  signal?: AbortSignal,
  workspaceId?: string
): Promise<ProviderModelsResponse> {
  switch (provider) {
    case 'base':
      return requestJson(getBaseProviderModelsContract, { signal })
    case 'ollama':
      return requestJson(getOllamaProviderModelsContract, { signal })
    case 'ollama-cloud':
      return requestJson(getOllamaCloudProviderModelsContract, {
        query: { workspaceId },
        signal,
      })
    case 'vllm':
      return requestJson(getVllmProviderModelsContract, { signal })
    case 'litellm':
      return requestJson(getLitellmProviderModelsContract, { signal })
    case 'openrouter':
      return requestJson(getOpenRouterProviderModelsContract, { signal })
    case 'openrouter-embeddings':
      return requestJson(getOpenRouterEmbeddingModelsContract, { signal })
    case 'fireworks':
      return requestJson(getFireworksProviderModelsContract, {
        query: { workspaceId },
        signal,
      })
    case 'together':
      return requestJson(getTogetherProviderModelsContract, {
        query: { workspaceId },
        signal,
      })
    case 'baseten':
      return requestJson(getBasetenProviderModelsContract, {
        query: { workspaceId },
        signal,
      })
  }
}

export function providerModelsQueryOptions(provider: ProviderModelSource, workspaceId?: string) {
  return queryOptions({
    queryKey: providerKeys.list(provider, workspaceId),
    queryFn: ({ signal }) => fetchProviderModels(provider, signal, workspaceId),
    staleTime: PROVIDER_MODELS_STALE_TIME,
  })
}

export function useProviderModels(provider: ProviderModelSource, workspaceId?: string) {
  return useQuery(providerModelsQueryOptions(provider, workspaceId))
}

/** Synchronous cache read for code paths which cannot use React hooks. */
export function getCachedProviderModels(
  provider: ProviderModelSource,
  workspaceId?: string
): string[] {
  return (
    getQueryClient().getQueryData<ProviderModelsResponse>(providerKeys.list(provider, workspaceId))
      ?.models ?? []
  )
}

let activeProviderWorkspaceId: string | undefined

/** Selects the workspace whose scoped provider cache may be read by non-React consumers. */
export function setActiveProviderWorkspaceId(workspaceId: string | undefined): void {
  activeProviderWorkspaceId = workspaceId
}

export function getActiveWorkspaceProviderModels(provider: ProviderModelSource): string[] {
  if (!activeProviderWorkspaceId) return []
  return getCachedProviderModels(provider, activeProviderWorkspaceId)
}

export function getCachedProviderModelInfo(
  provider: ProviderModelSource,
  workspaceId?: string
): ProviderModelsResponse['modelInfo'] {
  return getQueryClient().getQueryData<ProviderModelsResponse>(
    providerKeys.list(provider, workspaceId)
  )?.modelInfo
}
