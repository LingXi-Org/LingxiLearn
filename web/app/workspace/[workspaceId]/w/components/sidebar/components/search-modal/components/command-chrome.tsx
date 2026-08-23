import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react'
import { cn } from '@/components/ui-kit'

interface CommandListProps {
  children: ReactNode
  className?: string
  fade?: 'palette' | 'none'
}

export const CommandFadedList = forwardRef<HTMLDivElement, CommandListProps>(
  function CommandFadedList({ children, className }, ref) {
    return (
      <div ref={ref} className={cn('overflow-y-auto', className)}>
        {children}
      </div>
    )
  }
)

interface CommandSearchProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, 'onChange' | 'value'> {
  value: string
  onValueChange: (value: string) => void
  cycleResultsOnTab?: boolean
  surface?: 'palette' | 'default'
  endAdornment?: ReactNode
}

export const CommandSearch = forwardRef<HTMLInputElement, CommandSearchProps>(
  function CommandSearch(
    {
      value,
      onValueChange,
      cycleResultsOnTab: _cycleResultsOnTab,
      surface: _surface,
      endAdornment,
      ...props
    },
    ref
  ) {
    return (
      <div className='flex items-center border-t border-[var(--border-1)] px-3'>
        <input
          {...props}
          ref={ref}
          value={value}
          onChange={(event) => onValueChange(event.target.value)}
          className='h-11 min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-[var(--text-muted)]'
        />
        {endAdornment}
      </div>
    )
  }
)
