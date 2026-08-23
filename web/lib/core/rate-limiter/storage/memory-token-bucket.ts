import type {
  ConsumeResult,
  RateLimitStorageAdapter,
  TokenBucketConfig,
  TokenStatus,
} from './adapter'

interface BucketState {
  tokens: number
  lastRefillAt: number
}

/**
 * Process-local fallback for the UI runtime.
 *
 * The old fallback wrote token buckets to Web's Drizzle database. Web no
 * longer owns a domain database, so a process-local bucket is the only safe
 * fallback when Redis is not available. Shared deployments should configure
 * Redis; this adapter intentionally does not pretend to provide cross-process
 * coordination.
 */
export class MemoryTokenBucket implements RateLimitStorageAdapter {
  private readonly buckets = new Map<string, BucketState>()

  async consumeTokens(
    key: string,
    requestedTokens: number,
    config: TokenBucketConfig
  ): Promise<ConsumeResult> {
    const now = Date.now()
    const state = this.refill(key, config, now)
    const allowed = state.tokens >= requestedTokens
    if (allowed) state.tokens -= requestedTokens

    const resetAt = new Date(state.lastRefillAt + config.refillIntervalMs)
    return {
      allowed,
      tokensRemaining: Math.max(0, state.tokens),
      resetAt,
      retryAfterMs: allowed ? undefined : Math.max(0, resetAt.getTime() - now),
    }
  }

  async getTokenStatus(key: string, config: TokenBucketConfig): Promise<TokenStatus> {
    const now = Date.now()
    const state = this.refill(key, config, now)
    const nextRefillAt = new Date(state.lastRefillAt + config.refillIntervalMs)
    return {
      tokensAvailable: state.tokens,
      maxTokens: config.maxTokens,
      lastRefillAt: new Date(state.lastRefillAt),
      nextRefillAt,
    }
  }

  async resetBucket(key: string): Promise<void> {
    this.buckets.delete(key)
  }

  private refill(key: string, config: TokenBucketConfig, now: number): BucketState {
    const state = this.buckets.get(key) ?? { tokens: config.maxTokens, lastRefillAt: now }
    const elapsed = now - state.lastRefillAt
    const intervalsElapsed = Math.floor(elapsed / config.refillIntervalMs)
    if (intervalsElapsed > 0) {
      state.tokens = Math.min(
        config.maxTokens,
        state.tokens + intervalsElapsed * config.refillRate
      )
      state.lastRefillAt += intervalsElapsed * config.refillIntervalMs
    }
    this.buckets.set(key, state)
    return state
  }
}
