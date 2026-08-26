/** Slash command configuration. */
export interface SlashCommand {
  id: string
  label: string
}

export const TOP_LEVEL_COMMANDS: readonly SlashCommand[] = [
  { id: 'fast', label: 'Fast' },
  { id: 'research', label: 'Research' },
  { id: 'actions', label: 'Actions' },
] as const

/** Maps UI command IDs to API command IDs. */
export function getApiCommandId(uiCommandId: string): string {
  const commandMapping: Record<string, string> = {
    actions: 'superagent',
  }
  return commandMapping[uiCommandId] || uiCommandId
}

export const WEB_COMMANDS: readonly SlashCommand[] = [
  { id: 'search', label: 'Search' },
  { id: 'read', label: 'Read' },
  { id: 'scrape', label: 'Scrape' },
  { id: 'crawl', label: 'Crawl' },
] as const

export const ALL_SLASH_COMMANDS: readonly SlashCommand[] = [...TOP_LEVEL_COMMANDS, ...WEB_COMMANDS]

export const ALL_COMMAND_IDS = ALL_SLASH_COMMANDS.map((command) => command.id)

export function getCommandDisplayLabel(commandId: string): string {
  const command = ALL_SLASH_COMMANDS.find((candidate) => candidate.id === commandId)
  return command?.label || commandId.charAt(0).toUpperCase() + commandId.slice(1)
}

export const NEAR_TOP_THRESHOLD = 300

export const SCROLL_TOLERANCE = 8

export const MENU_STATE_TEXT_CLASSES = 'px-2 py-2 text-caption text-[var(--text-muted)]'

export function getNextIndex(current: number, direction: 'up' | 'down', maxIndex: number): number {
  if (direction === 'down') return current >= maxIndex ? 0 : current + 1
  return current <= 0 ? maxIndex : current - 1
}
