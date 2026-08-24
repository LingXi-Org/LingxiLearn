import type { KnowledgeBaseData } from '@/lib/knowledge/types'
import type { WorkspaceFolder } from '@/lib/folders/types'

/**
 * The folder tree the knowledge list navigates. One constant so the domain never spells
 * the resource type out ad hoc.
 */
export const KNOWLEDGE_FOLDER_RESOURCE_TYPE = 'knowledge_base' as const

/**
 * The knowledge-base folder tree is plain workspace folders — the domain-neutral
 * {@link WorkspaceFolder}, never a workflow-era type. Re-aliased here so the knowledge
 * domain reads its own model without importing the shared folder store directly.
 */
export type KnowledgeFolder = WorkspaceFolder

/** One row of the knowledge list, resolved to the entity it refers to. */
export type KnowledgeListItem =
  | { kind: 'base'; base: KnowledgeBaseData }
  | { kind: 'folder'; folder: KnowledgeFolder }

/**
 * Structured list filters, mirrored 1:1 from the URL (see `knowledgeParsers` in
 * `search-params.ts`). Every field is multi-select; an empty array means "no filter".
 */
export interface KnowledgeListFilters {
  /** Connector presence: `'connected'` / `'unconnected'`. */
  connector: string[]
  /** Document presence: `'has-docs'` / `'empty'`. */
  content: string[]
  /** Creator user ids. */
  owner: string[]
}
