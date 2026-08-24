'use client'

import type { WorkspaceFileRecord } from '@/lib/api/contracts/workspace-files'
import { ShareModal } from '@/app/workspace/[workspaceId]/files/components/share-modal'

export interface ShareModalHostProps {
  workspaceId: string
  /** Loaded files the `shareFileId` param resolves against. */
  files: WorkspaceFileRecord[]
  /** Deep-links a file's share dialog open; null keeps it closed. */
  shareFileId: string | null
  /** Clears the `shareFileId` URL param. */
  onClose: () => void
}

/**
 * Renders the share dialog when the `shareFileId` URL param resolves to a loaded file, in
 * both the list and the detail view. The dialog's open/close state lives entirely in the URL,
 * so a deep link opens it on load and closing it clears the param.
 */
export function ShareModalHost({ workspaceId, files, shareFileId, onClose }: ShareModalHostProps) {
  const shareFile = shareFileId ? (files.find((f) => f.id === shareFileId) ?? null) : null
  if (!shareFile) return null

  return (
    <ShareModal
      open
      onOpenChange={(open) => !open && onClose()}
      workspaceId={workspaceId}
      fileId={shareFile.id}
      fileName={shareFile.name}
      initialShare={shareFile.share ?? null}
    />
  )
}
