'use client'

export function useSSOProviders(_options?: { enabled?: boolean }): {
  data: { providers: Array<{ userId: string }> }
  isLoading: boolean
} {
  return { data: { providers: [] }, isLoading: false }
}
