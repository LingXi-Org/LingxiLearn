'use client'

import { Plus, Upload } from '@/components/ui-kit'
import { FolderPlus, Table as TableIcon } from '@/components/ui-kit/icons'
import { workspaceCopy } from '@/lib/product-copy'
import {
  type ChromeActionSpec,
  ResourceChromeFallback,
} from '@/app/workspace/[workspaceId]/components'

const copy = workspaceCopy.resources.tables

const COLUMNS = [
  { id: 'name', header: copy.columns.name },
  { id: 'columns', header: copy.columns.columns },
  { id: 'rows', header: copy.columns.rows },
  { id: 'created', header: copy.columns.created },
  { id: 'owner', header: workspaceCopy.common.columns.owner },
  { id: 'updated', header: copy.columns.updated },
]

const ACTIONS: ChromeActionSpec[] = [
  { text: workspaceCopy.resources.actions.importCsv, icon: Upload },
  { text: workspaceCopy.resources.actions.newFolder, icon: FolderPlus },
  { text: workspaceCopy.resources.actions.newTable, icon: Plus, variant: 'primary' },
]

export default function TablesLoading() {
  return (
    <ResourceChromeFallback
      icon={TableIcon}
      title={copy.title}
      columns={COLUMNS}
      actions={ACTIONS}
      searchPlaceholder={copy.searchPlaceholder}
      hasSort
      hasFilter
    />
  )
}
