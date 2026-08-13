/** Small SSR-safe storage helpers used by the public landing preview. */

export class BrowserStorage {
  static getItem<T>(key: string, fallback: T): T {
    if (typeof window === 'undefined') return fallback
    try {
      const raw = window.localStorage.getItem(key)
      if (raw === null) return fallback
      return JSON.parse(raw) as T
    } catch {
      return fallback
    }
  }

  static setItem<T>(key: string, value: T): boolean {
    if (typeof window === 'undefined') return false
    try {
      window.localStorage.setItem(key, JSON.stringify(value))
      return true
    } catch {
      return false
    }
  }

  static removeItem(key: string): boolean {
    if (typeof window === 'undefined') return false
    try {
      window.localStorage.removeItem(key)
      return true
    } catch {
      return false
    }
  }
}

const LANDING_PROMPT_KEY = 'lingxilearn.landing.prompt'

export class LandingPromptStorage {
  static store(prompt: string): boolean {
    const value = prompt.trim()
    return (
      value.length > 0 &&
      BrowserStorage.setItem(LANDING_PROMPT_KEY, { value, timestamp: Date.now() })
    )
  }

  static consume(maxAge = 24 * 60 * 60 * 1000): string | null {
    const stored = BrowserStorage.getItem<{ value?: string; timestamp?: number } | null>(
      LANDING_PROMPT_KEY,
      null
    )
    BrowserStorage.removeItem(LANDING_PROMPT_KEY)
    if (!stored?.value || !stored.timestamp || Date.now() - stored.timestamp > maxAge) return null
    return stored.value
  }
}
