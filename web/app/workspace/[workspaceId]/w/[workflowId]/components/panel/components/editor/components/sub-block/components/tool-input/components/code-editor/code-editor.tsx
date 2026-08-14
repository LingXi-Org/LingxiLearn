'use client'

export function CodeEditor({ value, onChange, placeholder, minHeight, disabled, onKeyDown }: any) {
  return (
    <textarea
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      disabled={disabled}
      onKeyDown={onKeyDown}
      className='min-h-[240px] w-full resize-y rounded-md border border-[var(--border)] bg-[var(--surface-1)] p-3 font-mono text-sm'
      style={{ minHeight }}
    />
  )
}
