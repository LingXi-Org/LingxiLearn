'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { SaveDiscardChips } from '@/components/settings/save-discard-actions'
import { ChipLink, toast } from '@/components/ui-kit'
import { ArrowLeft } from '@/components/ui-kit/icons'
import { createLogger } from '@/lib/logger'
import { userFacingError } from '@/lib/product-copy'
import { SkillTile } from '@/app/workspace/[workspaceId]/components'
import {
  CredentialDetailHeading,
  CredentialDetailLayout,
  UnsavedChangesModal,
  useUnsavedChangesGuard,
} from '@/app/workspace/[workspaceId]/components/credential-detail'
import {
  type SkillFieldErrors,
  SkillFields,
} from '@/app/workspace/[workspaceId]/skills/components/skill-fields'
import { SkillImportButton } from '@/app/workspace/[workspaceId]/skills/components/skill-import'
import {
  isSkillNameConflictError,
  type ParsedSkill,
  parseSkillMarkdown,
  validateSkillName,
} from '@/app/workspace/[workspaceId]/skills/components/utils'
import { useCreateSkill } from '@/hooks/queries/skills'
import { skillCopy } from '../components/skill-copy'

const logger = createLogger('SkillCreate')

interface SkillCreateProps {
  workspaceId: string
}

/**
 * Full-page skill creation, mirroring the skill detail surface: a fixed action
 * bar (Import / Discard / Create), a heading, and the editable Name / Description /
 * Content sections. Importing a SKILL.md prefills all three fields in place.
 */
export function SkillCreate({ workspaceId }: SkillCreateProps) {
  const router = useRouter()
  const skillsHref = `/workspace/${workspaceId}/skills`

  const createSkill = useCreateSkill()

  const [nameDraft, setNameDraft] = useState('')
  const [descriptionDraft, setDescriptionDraft] = useState('')
  const [contentDraft, setContentDraft] = useState('')
  /** Bumped to remount the seed-once rich Content editor on programmatic sets. */
  const [contentSeed, setContentSeed] = useState(0)
  const [errors, setErrors] = useState<SkillFieldErrors>({})

  const isDirty = !!nameDraft.trim() || !!descriptionDraft.trim() || !!contentDraft.trim()

  const guard = useUnsavedChangesGuard({ isDirty, backHref: skillsHref })

  const handleCreate = async () => {
    if (createSkill.isPending) return

    const newErrors: SkillFieldErrors = {}
    const nameError = validateSkillName(nameDraft)
    if (nameError) newErrors.name = nameError
    if (!descriptionDraft.trim()) newErrors.description = skillCopy.descriptionRequired
    if (!contentDraft.trim()) newErrors.content = skillCopy.contentRequired
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    try {
      const { created } = await createSkill.mutateAsync({
        workspaceId,
        skill: { name: nameDraft, description: descriptionDraft, content: contentDraft },
      })
      setErrors({})
      toast.success(`已创建“${nameDraft}”`)
      // Detach the guard so its Back trap can't fire mid-navigation; `replace` then
      // consumes the seeded entry rather than stacking another.
      guard.release()
      router.replace(created ? `${skillsHref}/${created.id}` : skillsHref)
    } catch (error) {
      if (isSkillNameConflictError(error)) {
        setErrors({ name: skillCopy.nameConflict })
      } else {
        toast.error('无法创建技能', {
          description: userFacingError(error, 'saveFailed'),
        })
      }
      logger.error('Failed to create skill', error)
    }
  }

  /** Applies a full skill shape to all three drafts and remounts the Content editor. */
  const seedDrafts = (source: Pick<ParsedSkill, 'name' | 'description' | 'content'>) => {
    setNameDraft(source.name)
    setDescriptionDraft(source.description)
    setContentDraft(source.content)
    setErrors({})
    setContentSeed((seed) => seed + 1)
  }

  /**
   * Pasting a full SKILL.md destructures it into the fields. Gated on a real
   * YAML `name:` key so a stray `---` or heading-only snippet pastes as
   * ordinary content instead of silently overwriting all three fields.
   */
  const handleContentPaste = (text: string): boolean => {
    const parsed = parseSkillMarkdown(text)
    if (!parsed.nameFromFrontmatter) return false
    seedDrafts(parsed)
    return true
  }

  const back = (
    <ChipLink href={skillsHref} onClick={guard.handleBackClick} leftIcon={ArrowLeft}>
      技能
    </ChipLink>
  )

  const handleDiscard = () => seedDrafts({ name: '', description: '', content: '' })

  const actions = (
    <>
      <SkillImportButton onImport={seedDrafts} disabled={createSkill.isPending} />
      <SaveDiscardChips
        dirty={isDirty}
        saving={createSkill.isPending}
        onSave={handleCreate}
        onDiscard={handleDiscard}
        creating
      />
    </>
  )

  return (
    <>
      <CredentialDetailLayout back={back} actions={actions}>
        <CredentialDetailHeading
          leading={<SkillTile />}
          title='新建技能'
          subtitle='编写技能，或导入已有的 SKILL.md'
        />

        <SkillFields
          name={nameDraft}
          description={descriptionDraft}
          content={contentDraft}
          onNameChange={(value) => {
            setNameDraft(value)
            if (errors.name) setErrors((prev) => ({ ...prev, name: undefined }))
          }}
          onDescriptionChange={(value) => {
            setDescriptionDraft(value)
            if (errors.description) setErrors((prev) => ({ ...prev, description: undefined }))
          }}
          onContentChange={(value) => {
            setContentDraft(value)
            if (errors.content) setErrors((prev) => ({ ...prev, content: undefined }))
          }}
          errors={errors}
          contentKey={contentSeed}
          workspaceId={workspaceId}
          disabled={createSkill.isPending}
          onPasteText={handleContentPaste}
        />
      </CredentialDetailLayout>

      <UnsavedChangesModal
        open={guard.showUnsavedAlert}
        onOpenChange={guard.setShowUnsavedAlert}
        onDiscard={guard.confirmDiscard}
      />
    </>
  )
}
