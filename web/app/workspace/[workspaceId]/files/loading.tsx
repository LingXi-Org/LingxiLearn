'use client'

import { File as FilesIcon, FolderPlus, Plus, Upload } from '@/components/ui-kit'
import { workspaceCopy } from '@/lib/product-copy'
import {
  type ChromeActionSpec,
  ResourceChromeFallback,
} from '@/app/workspace/[workspaceId]/components'

const copy = workspaceCopy.resources.files

const COLUMNS = [
  { id: 'name', header: copy.columns.name, widthMultiplier: 1.15 },
  { id: 'size', header: copy.columns.size, widthMultiplier: 0.85 },
  { id: 'type', header: copy.columns.type, widthMultiplier: 1.0 },
  { id: 'created', header: copy.columns.created },
  { id: 'owner', header: workspaceCopy.common.columns.owner },
  { id: 'updated', header: workspaceCopy.common.columns.updated },
]

const ACTIONS: ChromeActionSpec[] = [
  { text: workspaceCopy.resources.actions.upload, icon: Upload },
  { text: workspaceCopy.resources.actions.newFolder, icon: FolderPlus },
  { text: workspaceCopy.resources.actions.newFile, icon: Plus, variant: 'primary' },
]

export default function FilesLoading() {
  return (
    <ResourceChromeFallback
      icon={FilesIcon}
      title={copy.title}
      columns={COLUMNS}
      actions={ACTIONS}
      searchPlaceholder={copy.searchPlaceholder}
      hasSort
      hasFilter
    />
  )
}
