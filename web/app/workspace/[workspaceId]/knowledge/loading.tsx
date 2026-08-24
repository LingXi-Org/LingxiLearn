'use client'

import { Plus } from '@/components/ui-kit'
import { Database, FolderPlus } from '@/components/ui-kit/icons'
import { workspaceCopy } from '@/lib/product-copy'
import {
  type ChromeActionSpec,
  ResourceChromeFallback,
} from '@/app/workspace/[workspaceId]/components'
import { FOLDERED_RESOURCE_HEADERS } from '@/app/workspace/[workspaceId]/components/folders/foldered-resources'

const KNOWLEDGE_HEADER = FOLDERED_RESOURCE_HEADERS.knowledge_base
const copy = workspaceCopy.resources.knowledge

const COLUMNS = [
  { id: 'name', header: copy.columns.name },
  { id: 'documents', header: copy.columns.documents, widthMultiplier: 0.6 },
  { id: 'tokens', header: copy.columns.tokens, widthMultiplier: 0.6 },
  { id: 'connectors', header: '连接器', widthMultiplier: 0.7 },
  { id: 'created', header: copy.columns.created },
  { id: 'owner', header: workspaceCopy.common.columns.owner },
  { id: 'updated', header: workspaceCopy.common.columns.updated },
]

const ACTIONS: ChromeActionSpec[] = [
  { text: workspaceCopy.resources.actions.newFolder, icon: FolderPlus },
  { text: workspaceCopy.resources.actions.newBase, icon: Plus, variant: 'primary' },
]

export default function KnowledgeLoading() {
  return (
    <ResourceChromeFallback
      icon={Database}
      title={KNOWLEDGE_HEADER.rootLabel}
      columns={COLUMNS}
      actions={ACTIONS}
      searchPlaceholder={copy.searchPlaceholder}
      hasSort
      hasFilter
    />
  )
}
