import type { ComponentType } from 'react'
import { toSearchToken } from '@/lib/search/tokens'
import type { SearchBlockItem, SearchToolOperationItem } from '@/stores/modals/search/types'

// Re-export fuzzyMatch from shared layer for internal w/** compatibility
export { fuzzyMatch as fuzzyMatchImpl, type FuzzyResult } from '@/lib/search/fuzzy-match'

/**
 * Every result group the palette can render. This is also the canonical order:
 * the zero-query browse list and the flat search tie-break both follow it,
 * with two page-aware insertions at the front — the page's action group, then
 * its own entity section hoisted above `actions`' platform group.
 */
export const SEARCH_SECTIONS = [
  'actions',
  'blocks',
  'triggers',
  'tools',
  'toolOperations',
  'pages',
  'workflows',
  'workspaces',
  'files',
  'tables',
  'knowledgeBases',
  'logs',
  'connectedAccounts',
  'chats',
  'integrations',
] as const

/** A single search-modal result group. */
export type SearchSection = (typeof SEARCH_SECTIONS)[number]

/**
 * Canvas building-block sections. They render between the page's action group
 * and the Sim group; off the canvas they carry no items and render nothing.
 */
export const CANVAS_SECTIONS = ['blocks', 'triggers', 'tools', 'toolOperations'] as const

export interface IntegrationSearchItem {
  id: string
  name: string
  href: string
  icon: ComponentType<{ className?: string }>
  bgColor: string
}

export interface TaskItem {
  id: string
  name: string
  href: string
  /** Formatted last-activity date shown as trailing metadata. Set for chats. */
  date?: string
}

/**
 * A {@link TaskItem} that lives in a folder tree, so the row can show which
 * folder it came from — a name is only unique within its folder.
 */
export interface FolderedItem extends TaskItem {
  /** Owning folder names, root first. */
  folderPath?: string[]
}

export interface WorkflowItem extends FolderedItem {
  isCurrent?: boolean
}

export interface WorkspaceItem {
  id: string
  name: string
  href: string
  isCurrent?: boolean
  logoUrl?: string | null
  color?: string
}

export interface PageItem {
  id: string
  name: string
  icon: ComponentType<{ className?: string }>
  href?: string
  onClick?: () => void
  shortcut?: string
  hidden?: boolean
}

export type FileItem = FolderedItem

export interface LogItem {
  id: string
  /** Workflow (or job) name the execution belongs to. */
  name: string
  href: string
  /** Human-readable run date shown as trailing metadata. */
  date: string
}

/**
 * Pages that contribute their own palette actions while active. Each page
 * registers its handlers as global commands on mount; the palette invokes
 * them by id and only offers them while the matching route is mounted.
 */
export type PageActionContext =
  | 'workflow'
  | 'tables'
  | 'tableDetail'
  | 'files'
  | 'fileDetail'
  | 'knowledge'
  | 'knowledgeBase'
  | 'logs'
  | 'logsDashboard'

/** Where an {@link ActionItem} (a verb) is available. */
export type ActionContext = 'global' | PageActionContext

/**
 * An action is a verb the palette can run directly (create, import, toggle),
 * as opposed to an entity the user navigates to. Actions render at the top of
 * the result list so the most common "do something" intents are one keystroke
 * away.
 */
export interface ActionItem {
  id: string
  name: string
  /** Extra terms folded into the search value (e.g. "new add"). */
  keywords?: string
  /**
   * Lowercase queries that name this action outright — the module it heads
   * (`'workflows'` for Create workflow) or its bare verb (`'deploy'`,
   * `'copy'`). When the trimmed query IS one of these, the action ranks like
   * a page row ({@link PAGE_MATCH_TIER}), above section-lifted and
   * exact-name entity rows.
   */
  exactQueries?: readonly string[]
  icon: ComponentType<{ className?: string }>
  shortcut?: string
  context: ActionContext
  run: () => void
}

export type ActionGroupLabel = 'Sim' | 'Actions'

/**
 * The page's own entity section, hoisted directly under its action group in
 * both the browse list and the search tie-break.
 */
export const PAGE_CONTEXT_HOISTED_SECTION: Partial<Record<PageActionContext, SearchSection>> = {
  tables: 'tables',
  tableDetail: 'tables',
  files: 'files',
  fileDetail: 'files',
  knowledge: 'knowledgeBases',
  knowledgeBase: 'knowledgeBases',
  logs: 'logs',
  logsDashboard: 'logs',
}

/** Presentation group for an action without changing its stable result identity. */
export function getActionGroupLabel(action: ActionItem): ActionGroupLabel {
  return action.context === 'global' ? 'Sim' : 'Actions'
}

export interface SearchModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  workflows?: WorkflowItem[]
  workspaces?: WorkspaceItem[]
  chats?: TaskItem[]
  tables?: FolderedItem[]
  files?: FileItem[]
  knowledgeBases?: FolderedItem[]
  logs?: LogItem[]
  integrations?: IntegrationSearchItem[]
  connectedAccounts?: IntegrationSearchItem[]
  /** Page the palette was opened on, when that page contributes actions. */
  pageContext?: PageActionContext | null
  canEdit?: boolean
  canAdmin?: boolean
  onCreateWorkflow?: () => void
  onCreateFolder?: () => void
  onImportWorkflow?: () => void
}

export interface CommandItemProps {
  value: string
  onSelect: () => void
  icon: ComponentType<{ className?: string }>
  bgColor: string
  showColoredIcon?: boolean
  /**
   * Core workflow block type. Renders as the shared accent chip only when the
   * type has a mapped accent; unmapped types — every integration block — fall
   * back to their catalog `bgColor` tile.
   */
  workflowType?: string
  /** Primary text of the row. */
  label: string
  /** De-emphasized lead-in before the label (e.g. a tool operation's service). */
  labelPrefix?: string
  /** Right-aligned trailing metadata. */
  meta?: string
}

export const SECTION_LABELS: Record<SearchSection, string> = {
  actions: 'Sim',
  blocks: 'Blocks',
  triggers: 'Triggers',
  tools: 'Tools',
  toolOperations: 'Tool operations',
  pages: 'Pages',
  workflows: 'Workflows',
  workspaces: 'Workspaces',
  files: 'Files',
  tables: 'Tables',
  knowledgeBases: 'Knowledge Bases',
  logs: 'Logs',
  connectedAccounts: 'Connected Integrations',
  integrations: 'Integrations',
  chats: 'Chats',
}

export type SearchEntry =
  | { section: 'actions'; score: number; item: ActionItem }
  | { section: 'blocks' | 'tools' | 'triggers'; score: number; item: SearchBlockItem }
  | { section: 'toolOperations'; score: number; item: SearchToolOperationItem }
  | { section: 'connectedAccounts' | 'integrations'; score: number; item: IntegrationSearchItem }
  | { section: 'chats'; score: number; item: TaskItem }
  | { section: 'workflows'; score: number; item: WorkflowItem }
  | { section: 'tables' | 'knowledgeBases'; score: number; item: FolderedItem }
  | { section: 'files'; score: number; item: FileItem }
  | { section: 'logs'; score: number; item: LogItem }
  | { section: 'workspaces'; score: number; item: WorkspaceItem }
  | { section: 'pages'; score: number; item: PageItem }

export interface SearchEntryHandlers {
  onSelectAction: (item: ActionItem) => void
  onSelectBlock: (item: SearchBlockItem) => void
  onSelectTool: (item: SearchBlockItem) => void
  onSelectTrigger: (item: SearchBlockItem) => void
  onSelectToolOperation: (item: SearchToolOperationItem) => void
  onSelectConnectedAccount: (item: IntegrationSearchItem) => void
  onSelectIntegration: (item: IntegrationSearchItem) => void
  onSelectChat: (item: TaskItem) => void
  onSelectWorkflow: (item: WorkflowItem) => void
  onSelectTable: (item: FolderedItem) => void
  onSelectFile: (item: FileItem) => void
  onSelectKnowledgeBase: (item: FolderedItem) => void
  onSelectLog: (item: LogItem) => void
  onSelectWorkspace: (item: WorkspaceItem) => void
  onSelectPage: (item: PageItem) => void
}

/** Merge-ranks every match from the visible sections into one flat result list. */
export function getGlobalSearchResults(
  entriesBySection: Partial<Record<SearchSection, readonly SearchEntry[]>>,
  sections: readonly SearchSection[]
): SearchEntry[] {
  /* Flattening in section order makes the spec-stable sort's tie-break the
     section order (then within-section order) with no explicit comparator. */
  return sections
    .flatMap((section) => entriesBySection[section] ?? [])
    .sort((a, b) => b.score - a.score)
}

/**
 * `scroll-mt-12` mirrors the list's `pt-12`: the search input floats over the
 * top 48px of the scrollport, and cmdk keeps the selection visible with
 * `scrollIntoView({ block: 'nearest' })` — without the scroll margin, arrowing
 * upward (or loop-wrapping to the first row) parks the row under the input.
 * Group headings need the same margin because cmdk scrolls the heading into
 * view when the selection is its group's first row.
 */
export const GROUP_HEADING_CLASSNAME =
  '[&_[cmdk-group-heading]]:flex [&_[cmdk-group-heading]]:h-[18px] [&_[cmdk-group-heading]]:items-center [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:mb-2 [&_[cmdk-group-heading]]:scroll-mt-12 [&_[cmdk-group-heading]]:text-small [&_[cmdk-group-heading]]:text-[var(--text-muted)]'

export const COMMAND_ITEM_CLASSNAME =
  'group mx-0.5 flex h-[30px] w-full cursor-pointer items-center gap-2 rounded-lg border border-transparent px-2 text-left text-sm scroll-mt-12 scroll-mb-1.5 aria-selected:border-[var(--border-1)] aria-selected:bg-[var(--surface-active)] data-[disabled=true]:pointer-events-none data-[disabled=true]:opacity-50'

// Re-export fuzzyMatch from shared layer for internal w/** compatibility
export { fuzzyMatch as fuzzyMatchImpl, type FuzzyResult } from '@/lib/search/fuzzy-match'

/** Rank offset that lifts every name match above any secondary-text match. */
const NAME_MATCH_TIER = 1_000_000

/**
 * Rank offset that lifts an entire section above every name match when the
 * query IS that section's name — typing "triggers" asks for the Triggers
 * section itself, not rows from other sections that happen to contain the word.
 */
const SECTION_MATCH_TIER = 2_000_000

/**
 * Rank offset for a page row whose name IS the query. Typing "logs" means the
 * Logs page itself first, then its contents (the section lifted into
 * {@link SECTION_MATCH_TIER}) beneath it.
 */
export const PAGE_MATCH_TIER = 3_000_000

/**
 * Matches a query against secondary search text: a space-separated list of
 * entries where multi-word phrases are kebab-cased into single tokens (see
 * `toSearchToken`). Whole-string matching keeps the exact/prefix/substring and
 * multi-word token modes; scattered matching runs against each entry
 * individually, so a query can scatter within one entry ("sndmsg" →
 * "send-message") but never assemble itself across unrelated entries
 * ("whatsapp" must not match "wealthbox-write-contact match snap up").
 */
/**
 * Secondary-text strings are stable catalog data (block/tool/operation search
 * values), so their word splits are cached — the palette re-matches every
 * miss on every keystroke, and re-splitting dominated that loop.
 */
const secondaryTextWords = new Map<string, string[]>()

function matchSecondaryText(extra: string, query: string): FuzzyResult {
  const whole = fuzzyMatch(extra, query, { scatter: false })
  let best = whole.matched ? whole : NO_MATCH
  let words = secondaryTextWords.get(extra)
  if (!words) {
    words = extra.split(/\s+/)
    secondaryTextWords.set(extra, words)
  }
  for (const word of words) {
    const byWord = fuzzyMatch(word, query)
    if (byWord.matched && (!best.matched || byWord.score > best.score)) best = byWord
  }
  return best
}

/**
 * Ranks an item by its name first, falling back to secondary text (ids, aliases,
 * option labels) only when the name doesn't match — a name match always wins, so
 * an exact name hit isn't diluted by a long secondary string ("Agent" beats
 * "Pi Coding Agent" for the query "agent").
 */
function scoreItem(name: string, search: string, getExtra?: () => string | undefined): FuzzyResult {
  const byName = fuzzyMatch(name, search)
  if (byName.matched) {
    return { matched: true, score: byName.score + NAME_MATCH_TIER, positions: byName.positions }
  }
  const extra = getExtra?.()
  if (!extra) return NO_MATCH
  const byExtra = matchSecondaryText(extra, search)
  return byExtra.matched ? byExtra : NO_MATCH
}

/** Scores and sorts matches while retaining scores for cross-section ranking. */
export function scoreAndSort<T>(
  items: T[],
  toValue: (item: T) => string,
  search: string,
  toExtra?: (item: T) => string | undefined
): Array<{ item: T; score: number }> {
  const query = search.trim()
  const scored: Array<{ item: T; score: number }> = []
  for (const item of items) {
    const { matched, score } = scoreItem(
      toValue(item),
      query,
      toExtra ? () => toExtra(item) : undefined
    )
    if (matched) scored.push({ item, score })
  }
  scored.sort((a, b) => b.score - a.score)
  return scored
}

/**
 * Scores normal item matches first, then fills a matched section with its
 * remaining rows in natural order. A query that exactly names the section
 * lifts every returned row into {@link SECTION_MATCH_TIER}, keeping this
 * internal order but beating name matches from other sections.
 */
function scoreItemsForSection<T>(
  sectionLabel: string,
  items: T[],
  toValue: (item: T) => string,
  search: string,
  toExtra?: (item: T) => string | undefined,
  maxResults = Number.POSITIVE_INFINITY
): Array<{ item: T; score: number }> {
  const rankedItems = scoreAndSort(items, toValue, search, toExtra)
  const query = search.trim()
  const sectionMatch = fuzzyMatch(sectionLabel, query)
  const isExactLabelMatch =
    sectionMatch.matched && query.toLowerCase() === sectionLabel.toLowerCase()

  let results: Array<{ item: T; score: number }>
  if (!sectionMatch.matched || rankedItems.length >= maxResults) {
    results = rankedItems.slice(0, maxResults)
  } else {
    const matchedItems = new Set(rankedItems.map(({ item }) => item))
    const lowestItemScore = rankedItems.at(-1)?.score
    const fallbackScore =
      lowestItemScore === undefined
        ? sectionMatch.score
        : Math.min(sectionMatch.score, lowestItemScore - 1)

    results = [...rankedItems]
    for (const item of items) {
      if (!matchedItems.has(item)) results.push({ item, score: fallbackScore })
      if (results.length >= maxResults) break
    }
  }

  if (isExactLabelMatch) {
    return results.map(({ item }, index) => ({ item, score: SECTION_MATCH_TIER - index }))
  }
  return results
}

/**
 * Sections whose label never participates in matching. Tool operations are a
 * 1000+ registry-ordered list, so label-driven behavior ("tool operations"
 * lifting the section, or a partial hit like "tool" filling it) would surface
 * arbitrary rows; individual operations stay searchable by name and alias.
 */
const LABEL_MATCH_EXEMPT_SECTIONS = new Set<SearchSection>(['toolOperations'])

export function scoreSectionItems<T>(
  section: SearchSection,
  items: T[],
  toValue: (item: T) => string,
  search: string,
  toExtra?: (item: T) => string | undefined,
  maxResults = Number.POSITIVE_INFINITY
): Array<{ item: T; score: number }> {
  if (LABEL_MATCH_EXEMPT_SECTIONS.has(section)) {
    return scoreAndSort(items, toValue, search, toExtra).slice(0, maxResults)
  }
  return scoreItemsForSection(SECTION_LABELS[section], items, toValue, search, toExtra, maxResults)
}

/**
 * Rank offset added to every matched action. Actions are the palette's few
 * runnable verbs, so a matched action outranks entity rows of the same match
 * quality — a name-matched action beats name-matched entities, a
 * keyword-matched action beats other secondary-text matches — while the
 * half-tier offset deliberately cannot bridge into the next tier up
 * ({@link SECTION_MATCH_TIER}, {@link PAGE_MATCH_TIER}).
 */
export const ACTION_MATCH_BIAS = 500_000

/**
 * Scores actions by visible name before falling back to their keywords.
 * Every match is lifted by {@link ACTION_MATCH_BIAS}; a query listed in the
 * action's `exactQueries` ranks it like a page row instead.
 */
export function scoreActions(
  actions: ActionItem[],
  search: string,
  maxResults = Number.POSITIVE_INFINITY,
  groupLabel: ActionGroupLabel = 'Sim'
): Array<{ item: ActionItem; score: number }> {
  const query = search.trim().toLowerCase()
  return scoreItemsForSection(
    groupLabel,
    actions,
    (action) => action.name,
    search,
    (action) => `${toSearchToken(action.name)} ${action.keywords ?? ''}`,
    maxResults
  ).map(({ item, score }) => ({
    item,
    score: item.exactQueries?.includes(query) ? PAGE_MATCH_TIER : score + ACTION_MATCH_BIAS,
  }))
}

/**
 * Filters and ranks items by fuzzy match, highest score first; returns the input
 * unchanged when the search is empty or whitespace-only. Pass `toExtra` to rank
 * the name first and fall back to secondary text.
 */
export function filterAndSort<T>(
  items: T[],
  toValue: (item: T) => string,
  search: string,
  toExtra?: (item: T) => string | undefined
): T[] {
  if (!search.trim()) return items
  return scoreAndSort(items, toValue, search, toExtra).map((entry) => entry.item)
}

/**
 * Max rows rendered per group while searching. Re-rendering an unbounded,
 * reshuffling match set every keystroke is what stalls typing; results are
 * score-sorted, so the cap only drops the low-relevance tail.
 */
export const MAX_RESULTS_PER_GROUP = 50

/**
 * {@link filterAndSort} bounded to {@link MAX_RESULTS_PER_GROUP} while searching,
 * so the per-keystroke render can't block typing. The empty browse state is
 * returned in full.
 */
export function filterAndCap<T>(
  items: T[],
  toValue: (item: T) => string,
  search: string,
  toExtra?: (item: T) => string | undefined
): T[] {
  const results = filterAndSort(items, toValue, search, toExtra)
  return search.trim() ? results.slice(0, MAX_RESULTS_PER_GROUP) : results
}
