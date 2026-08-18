/**
 * The dedupe state machine behind `SessionProvider.refresh`, kept pure so it
 * is testable without React. Two independent guards collapse the `/api/v1/me`
 * request storm:
 *
 * - single-flight — concurrent refreshes share the one in-flight request;
 * - freshness — a completed revalidation stays fresh for
 *   {@link SESSION_REFRESH_FRESHNESS_MS}, so the `focus` + `visibilitychange`
 *   pair a tab return fires back to back costs one request, not two.
 *
 * Deliberately a timestamp comparison, not a cache framework.
 */

export interface RefreshDedupeState {
  /** The one in-flight revalidation, shared by concurrent asks. */
  inflight: Promise<unknown> | null
  /** Timestamp of the last completed revalidation attempt (success or failure). */
  lastRefreshAt: number
}

export interface RefreshDedupeDecision<TValue> {
  kind: 'fetch' | 'inflight' | 'fresh'
  /** Present for `inflight` (the shared request) and `fresh` (current state). */
  value?: Promise<TValue> | TValue
}

export function createRefreshDedupeState(): RefreshDedupeState {
  return { inflight: null, lastRefreshAt: 0 }
}

/** Decides whether a refresh ask must fetch, join a flight, or stay fresh. */
export function decideRefresh<TValue>(
  state: RefreshDedupeState,
  options: { force?: boolean; now: number; freshnessMs: number; current: TValue }
): RefreshDedupeDecision<TValue> {
  if (state.inflight) return { kind: 'inflight', value: state.inflight as Promise<TValue> }
  if (!options.force && options.now - state.lastRefreshAt < options.freshnessMs) {
    return { kind: 'fresh', value: options.current }
  }
  return { kind: 'fetch' }
}

/** Starts the fetch decided by {@link decideRefresh} and wires the bookkeeping. */
export function trackRefresh<TValue>(
  state: RefreshDedupeState,
  request: Promise<TValue>,
  now: () => number
): Promise<TValue> {
  state.inflight = request
  // The bookkeeping chain is a DERIVED promise: swallow its rejection so a
  // failed revalidation only surfaces through the original `request`, which
  // every waiter (including the caller) already handles.
  void request
    .finally(() => {
      state.lastRefreshAt = now()
      if (state.inflight === request) state.inflight = null
    })
    .catch(() => {})
  return request
}

/**
 * A resource-call 401 means the session changed under us; the freshness
 * window must not block the revalidation that follows.
 */
export function invalidateRefreshFreshness(state: RefreshDedupeState): void {
  state.lastRefreshAt = 0
}
