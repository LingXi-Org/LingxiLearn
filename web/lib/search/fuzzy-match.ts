/**
 * Fuzzy matching utilities for search and autocomplete.
 */

/** Characters that begin a new word — a match here scores higher. */
const SEPARATORS = new Set([' ', '-', '_', '/', '.', ':', '(', ')'])

/** Result of matching a query against a single candidate string. */
export interface FuzzyResult {
  /** Whether every query character was found, in order. */
  matched: boolean
  /** Relative ranking score; higher sorts first. Only meaningful when matched. */
  score: number
  /** Indices into the candidate string that matched, ascending. Read-only. */
  positions: readonly number[]
}

/**
 * Shared singleton for the no-match case. The frozen empty array makes the
 * read-only contract explicit and guarantees the shared instance can never be
 * mutated by a caller.
 */
const NO_MATCH: FuzzyResult = { matched: false, score: 0, positions: Object.freeze([]) }

function isCamelBoundary(text: string, index: number): boolean {
  if (index === 0) return false
  const prev = text[index - 1]
  const curr = text[index]
  return prev === prev.toLowerCase() && curr === curr.toUpperCase()
}

function isHardBoundary(text: string, index: number): boolean {
  if (index === 0) return true
  const prev = text[index - 1]
  return SEPARATORS.has(prev) || isCamelBoundary(text, index)
}

/**
 * Order-independent token fallback for multi-word queries.
 * Matches when any permutation of query tokens appears in text.
 */
function tokenFallback(lowerText: string, lowerQuery: string): FuzzyResult {
  const queryTokens = lowerQuery.split(/\s+/).filter(Boolean)
  if (queryTokens.length === 1) return NO_MATCH

  const textTokens = lowerText.split(/\s+/).filter(Boolean)
  const tokenPositions = new Set<number>()

  for (const token of queryTokens) {
    const start = lowerText.indexOf(token)
    if (start === -1) return NO_MATCH
    for (let k = 0; k < token.length; k++) tokenPositions.add(start + k)
  }

  return {
    matched: true,
    score: 10 - lowerText.length * 0.1,
    positions: Array.from(tokenPositions).sort((a, b) => a - b),
  }
}

/**
 * Subsequence fuzzy match with positional scoring. Rewards matches at word
 * boundaries (`slk` → **S**lack), consecutive runs, and prefix/exact hits,
 * while still matching scattered characters so typos and partial recall work.
 *
 * Exact, prefix, contains, and multi-word token matches all reproduce the
 * original substring matcher's behavior, making this a strict superset: any
 * result the old matcher returned, this one returns too. The only additions are
 * scattered subsequences, and those are accepted only when the match STARTS at a
 * hard word boundary — so initialisms match (`slk` → **S**la**c**k) but loose
 * noise does not (`slack` will not scatter-match "Page**S**peed", and `se` will
 * not match every item containing s…e).
 *
 * Falls back to order-independent token matching for multi-word queries
 * (`message slack` matches "Slack Send Message") which a strict left-to-right
 * subsequence would miss.
 *
 * Contiguous substring matches report the indices of the substring itself
 * rather than an earlier scattered occurrence of the same characters.
 *
 * Pass `scatter: false` to skip the scattered-subsequence mode. Over long
 * multi-word text (alias lists, option labels) a scattered query matches
 * almost anything — "whatsapp" finds `w…h…a…t…s…a…p…p` across unrelated alias
 * words — so secondary-text matching keeps only the exact/prefix/substring
 * and multi-word token modes.
 */
export function fuzzyMatch(
  text: string,
  query: string,
  options?: { scatter?: boolean }
): FuzzyResult {
  if (!query) return { matched: true, score: 1, positions: [] }
  if (!text) return NO_MATCH

  const lowerText = text.toLowerCase()
  const lowerQuery = query.toLowerCase()

  const substringIndex = lowerText.indexOf(lowerQuery)
  if (substringIndex !== -1) {
    const length = lowerQuery.length
    const positions = Array.from({ length }, (_, k) => substringIndex + k)

    let score = 1
    if (substringIndex === 0) score += 10
    else if (SEPARATORS.has(lowerText[substringIndex - 1])) score += 8
    else if (isCamelBoundary(text, substringIndex)) score += 6
    score += (length - 1) * 6

    if (lowerText === lowerQuery) score += 120
    else if (substringIndex === 0) score += 50
    else score += 25

    score -= substringIndex * 0.5
    score -= (length - 1) * 0.15
    score -= lowerText.length * 0.1
    return { matched: true, score, positions }
  }

  if (options?.scatter === false) return tokenFallback(lowerText, lowerQuery)

  const positions: number[] = []
  let queryIndex = 0
  let score = 0
  let prevMatch = -2

  for (let i = 0; i < lowerText.length && queryIndex < lowerQuery.length; i++) {
    if (lowerText[i] !== lowerQuery[queryIndex]) continue

    let charScore = 1
    if (i === 0) charScore += 10
    else if (SEPARATORS.has(lowerText[i - 1])) charScore += 8
    else if (isCamelBoundary(text, i)) charScore += 6
    if (prevMatch === i - 1) charScore += 5

    score += charScore
    positions.push(i)
    prevMatch = i
    queryIndex++
  }

  if (queryIndex === lowerQuery.length && isHardBoundary(lowerText, positions[0])) {
    score -= positions[0] * 0.5
    score -= (positions[positions.length - 1] - positions[0]) * 0.15
    score -= lowerText.length * 0.1
    return { matched: true, score, positions }
  }

  return tokenFallback(lowerText, lowerQuery)
}