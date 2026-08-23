export type ChunkingStrategy = 'auto' | 'text' | 'regex' | 'recursive' | 'sentence' | 'token'

export type RecursiveRecipe = 'plain' | 'markdown' | 'code'

export interface StrategyOptions {
  pattern?: string
  separators?: string[]
  recipe?: RecursiveRecipe
  strictBoundaries?: boolean
}
