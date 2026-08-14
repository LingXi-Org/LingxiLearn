'use client'

export function useForkingAvailability() {
  return { available: false, isLoading: false }
}

export function useForkingAvailable(_workspaceId?: string): boolean {
  return false
}
