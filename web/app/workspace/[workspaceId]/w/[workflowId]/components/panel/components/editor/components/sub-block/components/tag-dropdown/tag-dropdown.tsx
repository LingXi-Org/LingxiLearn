'use client'

export function checkTagTrigger(text: string, cursorPosition: number) {
  const beforeCursor = text.slice(0, cursorPosition)
  const match = beforeCursor.match(/<([\w-]*)$/)
  return { show: Boolean(match), searchTerm: match?.[1] ?? '' }
}

export function TagDropdown({ visible, onSelect, onClose, className, style }: any) {
  if (!visible) return null
  return <div className={className} style={style} role='listbox' onClick={onClose}>{null}</div>
}
