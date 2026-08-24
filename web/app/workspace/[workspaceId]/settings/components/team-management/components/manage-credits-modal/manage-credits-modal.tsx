'use client'

import { useEffect, useRef, useState } from 'react'
import {
  ChipModal,
  ChipModalBody,
  ChipModalError,
  ChipModalField,
  ChipModalFooter,
  ChipModalHeader,
  Info,
} from '@/components/ui-kit'
import { userFacingError } from '@/lib/product-copy'
import {
  useOrganizationMemberUsageLimit,
  useUpdateOrganizationMemberUsageLimit,
} from '@/hooks/queries/organization'

export interface ManageCreditsTarget {
  userId: string
  name: string
  email: string
}

interface ManageCreditsModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  organizationId: string
  member: ManageCreditsTarget | null
}

/**
 * Modal for viewing a member's credits used in the organization's workspaces and
 * setting their per-member credit limit. "Credits used" is a read-only chip;
 * "Credit limit" is editable (blank = no limit). Hosted-only feature — surfaced
 * only from the Organization tab, which already requires hosted + Team plan.
 */
export function ManageCreditsModal({
  open,
  onOpenChange,
  organizationId,
  member,
}: ManageCreditsModalProps) {
  const userId = member?.userId
  const { data, isLoading } = useOrganizationMemberUsageLimit(organizationId, userId, open)
  const updateLimit = useUpdateOrganizationMemberUsageLimit()

  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)
  // Seed the draft from server data only until the admin starts typing, so a
  // background refetch (window focus, post-save invalidation) can't clobber an
  // in-progress edit. Reset when the modal closes.
  const hasEditedRef = useRef(false)

  useEffect(() => {
    if (!open) {
      hasEditedRef.current = false
      return
    }
    if (data && !hasEditedRef.current) {
      setDraft(data.creditLimit === null ? '' : String(data.creditLimit))
      setError(null)
    }
  }, [open, data])

  const trimmed = draft.trim()
  const parsedLimit = trimmed === '' ? null : Number(trimmed)
  const isValid =
    trimmed === '' || (parsedLimit !== null && Number.isInteger(parsedLimit) && parsedLimit >= 0)
  const currentLimit = data?.creditLimit ?? null
  const isDirty = parsedLimit !== currentLimit
  const isSaving = updateLimit.isPending

  const creditsUsed = data ? data.creditsUsed.toLocaleString() : '—'
  const creditsUsedTitle = data
    ? `本${data.billingInterval === 'year' ? '年' : '月'}已使用额度`
    : '已使用额度'

  const handleSave = () => {
    if (!userId) return
    if (!isValid) {
      setError('请输入整数额度，留空表示不设上限。')
      return
    }
    setError(null)
    updateLimit.mutate(
      { orgId: organizationId, userId, creditLimit: parsedLimit },
      {
        onSuccess: () => onOpenChange(false),
        onError: (err) => setError(userFacingError(err, 'saveFailed')),
      }
    )
  }

  return (
    <ChipModal open={open} onOpenChange={onOpenChange} srTitle='管理额度'>
      <ChipModalHeader onClose={() => onOpenChange(false)}>
        {member ? `管理额度 — ${member.name || member.email}` : '管理额度'}
      </ChipModalHeader>
      <ChipModalBody>
        <ChipModalField
          type='copy'
          title={creditsUsedTitle}
          value={isLoading ? '正在加载…' : creditsUsed}
          copyLabel='复制已使用额度'
        />
        <ChipModalField
          type='input'
          inputType='number'
          title={
            <span className='inline-flex items-center gap-1.5'>
              额度上限
              <Info side='top'>
                以额度为单位设置。该上限会限制此成员在每个计费周期内使用组织工作区的总额度。
              </Info>
            </span>
          }
          value={draft}
          onChange={(value) => {
            hasEditedRef.current = true
            setDraft(value)
          }}
          placeholder='不设上限'
          hint='留空表示不设上限。'
          disabled={isLoading || isSaving}
        />
        <ChipModalError>{error}</ChipModalError>
      </ChipModalBody>
      <ChipModalFooter
        onCancel={() => onOpenChange(false)}
        cancelDisabled={isSaving}
        primaryAction={{
          label: isSaving ? '正在保存…' : '保存',
          onClick: handleSave,
          disabled: !isValid || !isDirty || isSaving || isLoading,
        }}
      />
    </ChipModal>
  )
}
