/**
 * Resolves after `ms` milliseconds, or as soon as `signal` aborts.
 *
 * This is intentionally domain-neutral: retry and polling loops in any
 * application-owned runtime can use it without depending on a retired
 * feature package.
 */
export function sleepUntilAborted(ms: number, signal: AbortSignal): Promise<void> {
  if (signal.aborted || ms <= 0) return Promise.resolve()

  return new Promise<void>((resolve) => {
    let settled = false

    const cleanup = () => {
      clearTimeout(timer)
      signal.removeEventListener('abort', onAbort)
    }

    const settle = () => {
      if (settled) return
      settled = true
      cleanup()
      resolve()
    }

    const onAbort = () => settle()
    const timer = setTimeout(settle, ms)
    signal.addEventListener('abort', onAbort, { once: true })

    // Close the race between the initial check and listener registration.
    if (signal.aborted) onAbort()
  })
}
