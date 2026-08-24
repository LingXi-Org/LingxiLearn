'use client'

import { useState } from 'react'
import { ChipModalField } from '@/components/ui-kit'
import { userFacingError } from '@/lib/product-copy'
import {
  type ParsedSkill,
  readSkillFile,
  SKILL_IMPORT_ACCEPT,
} from '@/app/workspace/[workspaceId]/skills/components/utils'

interface SkillImportProps {
  onImport: (data: ParsedSkill) => void
}

/**
 * The canvas modal's Import tab: a single file field that reads a SKILL.md (or
 * a ZIP containing one) into the create form. The full-page create surface uses
 * {@link SkillImportButton} in its action bar instead of a field.
 */
export function SkillImport({ onImport }: SkillImportProps) {
  const [importing, setImporting] = useState(false)
  const [error, setError] = useState('')

  const handleFiles = async (files: File[]) => {
    const file = files[0]
    if (!file) return

    setImporting(true)
    setError('')
    try {
      onImport(await readSkillFile(file))
    } catch (error) {
      setError(userFacingError(error, 'uploadFailed'))
    } finally {
      setImporting(false)
    }
  }

  return (
    <ChipModalField
      type='file'
      title='上传文件'
      accept={SKILL_IMPORT_ACCEPT}
      onChange={(files) => void handleFiles(files)}
      loading={importing}
      label={importing ? '正在导入…' : undefined}
      description='带 YAML 前置元数据的 .md 文件，或包含 SKILL.md 的 .zip 文件'
      error={error || undefined}
    />
  )
}
