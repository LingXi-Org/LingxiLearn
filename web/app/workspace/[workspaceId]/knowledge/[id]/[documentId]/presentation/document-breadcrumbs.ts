import type { BreadcrumbItem } from '@/app/workspace/[workspaceId]/components'
import {
  FOLDERED_RESOURCE_HEADERS,
  folderBreadcrumbItems,
} from '@/app/workspace/[workspaceId]/components/folders'

interface DocumentTrailParams {
  /** The knowledge base's folder trail from `useFolderAncestors`. */
  folderChain: Parameters<typeof folderBreadcrumbItems>[0]['breadcrumbs']
  onNavigateFolder: (folderId: string | null) => void
  knowledgeBaseCrumbLabel: string
  knowledgeBaseCrumbIcon: BreadcrumbItem['icon']
  documentCrumbLabel: string
  documentIcon: BreadcrumbItem['icon']
  onKnowledgeBaseClick: () => void
}

/**
 * `Knowledge Base / …the base's folders / <base> / <last>`. Every view on the
 * document route is that trail with a different last crumb — the document, a
 * chunk, an error, a loading placeholder — so it is built once here rather
 * than restated per view.
 */
export function buildDocumentTrail(
  params: DocumentTrailParams,
  last: BreadcrumbItem,
  onDocumentClick?: () => void
): BreadcrumbItem[] {
  return folderBreadcrumbItems({
    rootLabel: FOLDERED_RESOURCE_HEADERS.knowledge_base.rootLabel,
    rootIcon: FOLDERED_RESOURCE_HEADERS.knowledge_base.rootIcon,
    breadcrumbs: params.folderChain,
    onNavigate: params.onNavigateFolder,
    trailing: [
      {
        label: params.knowledgeBaseCrumbLabel,
        icon: params.knowledgeBaseCrumbIcon,
        onClick: params.onKnowledgeBaseClick,
      },
      /** Omitted when the document IS the last crumb — you are already on it. */
      ...(onDocumentClick
        ? [
            {
              label: params.documentCrumbLabel,
              icon: params.documentIcon,
              onClick: onDocumentClick,
            },
          ]
        : []),
      last,
    ],
  })
}
