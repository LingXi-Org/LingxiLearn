import type { ComponentType } from 'react'
import { memo } from 'react'
import { cn } from '@/components/ui-kit'
import { Command } from 'cmdk'

interface ActionItemProps {
  value: string
  onSelect: () => void
  icon: ComponentType<{ className?: string }>
  name: string
}

export const MemoizedActionItem = memo(function MemoizedActionItem({
  value,
  onSelect,
  icon: Icon,
  name,
}: ActionItemProps) {
  return (
    <Command.Item
      value={value}
      onSelect={onSelect}
      className={cn(
        'flex h-9 cursor-pointer items-center gap-2 rounded-md px-2 text-sm',
        'aria-selected:bg-[var(--surface-active)]'
      )}
    >
      <Icon className='size-4 text-[var(--text-muted)]' />
      <span className='truncate'>{name}</span>
    </Command.Item>
  )
})
