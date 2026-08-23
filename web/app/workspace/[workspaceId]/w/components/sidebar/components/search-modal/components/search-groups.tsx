import type { ComponentType, ReactNode } from 'react'
import { cn } from '@/components/ui-kit'
import { Command } from 'cmdk'
import type { SearchEntry, SearchEntryHandlers } from '../utils'

interface SearchEntryGroupProps {
  variant: 'results' | 'section'
  heading?: string
  entries: readonly SearchEntry[]
  handlers: SearchEntryHandlers
}

interface RenderedEntry {
  id: string
  label: string
  meta?: string
  icon: ComponentType<{ className?: string }>
  onSelect: () => void
}

function renderEntry(entry: SearchEntry, handlers: SearchEntryHandlers): RenderedEntry {
  switch (entry.section) {
    case 'actions':
      return {
        id: entry.item.id,
        label: entry.item.name,
        meta: entry.item.shortcut,
        icon: entry.item.icon,
        onSelect: () => handlers.onSelectAction(entry.item),
      }
    case 'blocks':
      return {
        id: entry.item.id,
        label: entry.item.name,
        icon: entry.item.icon,
        onSelect: () => handlers.onSelectBlock(entry.item),
      }
    case 'tools':
      return {
        id: entry.item.id,
        label: entry.item.name,
        icon: entry.item.icon,
        onSelect: () => handlers.onSelectTool(entry.item),
      }
    case 'triggers':
      return {
        id: entry.item.id,
        label: entry.item.name,
        icon: entry.item.icon,
        onSelect: () => handlers.onSelectTrigger(entry.item),
      }
    case 'toolOperations':
      return {
        id: entry.item.id,
        label: entry.item.name,
        meta: entry.item.serviceName,
        icon: entry.item.icon,
        onSelect: () => handlers.onSelectToolOperation(entry.item),
      }
    case 'connectedAccounts':
      return {
        id: entry.item.id,
        label: entry.item.name,
        icon: entry.item.icon,
        onSelect: () => handlers.onSelectConnectedAccount(entry.item),
      }
    case 'integrations':
      return {
        id: entry.item.id,
        label: entry.item.name,
        icon: entry.item.icon,
        onSelect: () => handlers.onSelectIntegration(entry.item),
      }
    case 'chats':
      return {
        id: entry.item.id,
        label: entry.item.name,
        meta: entry.item.date,
        icon: PlaceholderIcon,
        onSelect: () => handlers.onSelectChat(entry.item),
      }
    case 'workflows':
      return {
        id: entry.item.id,
        label: entry.item.name,
        meta: entry.item.folderPath?.join(' / '),
        icon: PlaceholderIcon,
        onSelect: () => handlers.onSelectWorkflow(entry.item),
      }
    case 'tables':
      return {
        id: entry.item.id,
        label: entry.item.name,
        meta: entry.item.folderPath?.join(' / '),
        icon: PlaceholderIcon,
        onSelect: () => handlers.onSelectTable(entry.item),
      }
    case 'files':
      return {
        id: entry.item.id,
        label: entry.item.name,
        meta: entry.item.folderPath?.join(' / '),
        icon: PlaceholderIcon,
        onSelect: () => handlers.onSelectFile(entry.item),
      }
    case 'knowledgeBases':
      return {
        id: entry.item.id,
        label: entry.item.name,
        meta: entry.item.folderPath?.join(' / '),
        icon: PlaceholderIcon,
        onSelect: () => handlers.onSelectKnowledgeBase(entry.item),
      }
    case 'logs':
      return {
        id: entry.item.id,
        label: entry.item.name,
        meta: entry.item.date,
        icon: PlaceholderIcon,
        onSelect: () => handlers.onSelectLog(entry.item),
      }
    case 'workspaces':
      return {
        id: entry.item.id,
        label: entry.item.name,
        icon: PlaceholderIcon,
        onSelect: () => handlers.onSelectWorkspace(entry.item),
      }
    case 'pages':
      return {
        id: entry.item.id,
        label: entry.item.name,
        meta: entry.item.shortcut,
        icon: entry.item.icon,
        onSelect: () => handlers.onSelectPage(entry.item),
      }
  }
}

function PlaceholderIcon({ className }: { className?: string }) {
  return (
    <span aria-hidden='true' className={cn('size-4 rounded bg-[var(--surface-3)]', className)} />
  )
}

export function SearchEntryGroup({ variant, heading, entries, handlers }: SearchEntryGroupProps) {
  const content: ReactNode = entries.map((entry) => {
    const rendered = renderEntry(entry, handlers)
    const Icon = rendered.icon
    return (
      <Command.Item
        key={`${entry.section}:${rendered.id}`}
        value={`${entry.section}:${rendered.id}:${rendered.label}`}
        onSelect={rendered.onSelect}
        className={cn(
          'flex h-9 cursor-pointer items-center gap-2 rounded-md px-2 text-sm',
          'aria-selected:bg-[var(--surface-active)]'
        )}
      >
        <Icon className='size-4 flex-shrink-0 text-[var(--text-muted)]' />
        <span className='min-w-0 flex-1 truncate'>{rendered.label}</span>
        {rendered.meta ? (
          <span className='max-w-[45%] truncate text-[var(--text-muted)] text-xs'>
            {rendered.meta}
          </span>
        ) : null}
      </Command.Item>
    )
  })

  return (
    <Command.Group
      heading={variant === 'section' ? heading : undefined}
      className='px-1 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1 [&_[cmdk-group-heading]]:text-[var(--text-muted)] [&_[cmdk-group-heading]]:text-xs'
    >
      {content}
    </Command.Group>
  )
}
