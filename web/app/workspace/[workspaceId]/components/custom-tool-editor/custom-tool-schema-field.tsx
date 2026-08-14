'use client'

import { SCHEMA_PLACEHOLDER } from '@/app/workspace/[workspaceId]/components/custom-tool-editor/custom-tool-schema'
import type { useSchemaGeneration } from '@/app/workspace/[workspaceId]/components/custom-tool-editor/use-custom-tool-generation'

const CodeEditor = ({ value, onChange, placeholder, minHeight, disabled, error }: any) => (
  <textarea
    value={value}
    onChange={(event) => onChange(event.target.value)}
    placeholder={placeholder}
    disabled={disabled}
    aria-invalid={error}
    className='min-h-[240px] w-full resize-y rounded-md border border-[var(--border)] bg-[var(--surface-1)] p-3 font-mono text-sm'
    style={{ minHeight }}
  />
)

interface CustomToolSchemaFieldProps {
  value: string
  onChange: (value: string) => void
  error: boolean
  generation: ReturnType<typeof useSchemaGeneration>
  /** Renders the editor inert for viewers without edit rights. */
  disabled?: boolean
}

/**
 * The JSON-schema half of the custom tool editor. The surrounding surface owns
 * the section label, the "Generate" action, and the error message — this field
 * is just the editor, so both consumers can frame it however they need.
 */
export function CustomToolSchemaField({
  value,
  onChange,
  error,
  generation,
  disabled = false,
}: CustomToolSchemaFieldProps) {
  const busy = disabled || generation.isLoading || generation.isStreaming

  return (
    <CodeEditor
      value={value}
      onChange={onChange}
      language='json'
      placeholder={SCHEMA_PLACEHOLDER}
      minHeight='420px'
      error={error}
      disabled={busy}
    />
  )
}
