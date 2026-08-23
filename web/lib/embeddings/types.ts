/**
 * Provider-agnostic embedding types shared by transport contracts and the
 * Embeddings block. Provider execution is owned by the API service; this
 * module deliberately contains no request/adapter runtime types.
 */

export type EmbeddingProviderKind =
  | 'openai'
  | 'azure-openai'
  | 'openrouter'
  | 'gemini'
  | 'cohere'
  | 'mistral'

/**
 * Providers a catalog model can belong to. Azure OpenAI and OpenRouter are
 * transports for OpenAI models, so no model is catalogued under either one.
 */
export type EmbeddingCatalogProvider = Exclude<EmbeddingProviderKind, 'azure-openai' | 'openrouter'>

/** Provider id for `estimateTokenCount` so token counts match the embedding provider's tokenization. */
export type TokenizerProviderId = 'openai' | 'google' | 'cohere' | 'mistral'

/**
 * What the embedding will be used for. Providers that support task-conditioned
 * embeddings map these onto their own enum; providers that do not ignore it.
 */
export type EmbeddingTaskType =
  | 'document'
  | 'query'
  | 'similarity'
  | 'classification'
  | 'clustering'
