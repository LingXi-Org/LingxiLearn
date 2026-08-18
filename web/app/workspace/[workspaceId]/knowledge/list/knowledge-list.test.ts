/**
 * @vitest-environment node
 */
import { describe, expect, it } from 'vitest'
import {
  applyKnowledgeBaseFilters,
  filterKnowledgeBases,
  knowledgeBasesInFolder,
  visibleKnowledgeFolders,
} from '@/app/workspace/[workspaceId]/knowledge/list/filters'
import { decorateKnowledgeListItems } from '@/app/workspace/[workspaceId]/knowledge/list/sort'
import type { KnowledgeFolder, KnowledgeListFilters } from '@/app/workspace/[workspaceId]/knowledge/list/types'
import type { KnowledgeBaseData } from '@/lib/knowledge/types'

function makeBase(id: string, overrides: Partial<KnowledgeBaseData> = {}): KnowledgeBaseData {
  return {
    id,
    userId: 'u-1',
    name: id,
    description: '',
    tokenCount: 0,
    embeddingModel: 'text-embedding',
    embeddingDimension: 1024,
    chunkingConfig: {},
    createdAt: '2026-01-01T00:00:00.000Z',
    updatedAt: '2026-01-01T00:00:00.000Z',
    deletedAt: null,
    workspaceId: 'ws-1',
    folderId: null,
    ...overrides,
  }
}

function makeFolder(
  id: string,
  parentId: string | null = null,
  overrides: Partial<KnowledgeFolder> = {}
): KnowledgeFolder {
  return {
    id,
    name: id,
    userId: 'u-1',
    workspaceId: 'ws-1',
    parentId,
    resourceType: 'knowledge_base',
    locked: false,
    sortOrder: 0,
    createdAt: new Date('2026-01-01T00:00:00.000Z'),
    updatedAt: new Date('2026-01-01T00:00:00.000Z'),
    deletedAt: null,
    ...overrides,
  }
}

const NO_FILTERS: KnowledgeListFilters = { connector: [], content: [], owner: [] }

describe('filterKnowledgeBases', () => {
  it('returns everything on an empty query', () => {
    const bases = [makeBase('kb-1'), makeBase('kb-2')]
    expect(filterKnowledgeBases(bases, '  ')).toEqual(bases)
  })

  it('matches name or description, case-insensitively', () => {
    const bases = [
      makeBase('kb-1', { name: 'Physics Notes' }),
      makeBase('kb-2', { name: 'Chemistry', description: 'physics experiments' }),
      makeBase('kb-3', { name: 'History' }),
    ]
    expect(filterKnowledgeBases(bases, 'PHYSICS').map((kb) => kb.id)).toEqual(['kb-1', 'kb-2'])
  })
})

describe('visibleKnowledgeFolders', () => {
  it('only shows siblings of the open folder', () => {
    const folders = [makeFolder('f-root-1'), makeFolder('f-child', 'f-root-1')]
    expect(visibleKnowledgeFolders(folders, null, '').map((f) => f.id)).toEqual(['f-root-1'])
    expect(visibleKnowledgeFolders(folders, 'f-root-1', '').map((f) => f.id)).toEqual(['f-child'])
  })

  it('filters siblings by the search term', () => {
    const folders = [makeFolder('Alpha', null, { name: 'Alpha' }), makeFolder('Beta', null, { name: 'Beta' })]
    expect(visibleKnowledgeFolders(folders, null, 'alp').map((f) => f.id)).toEqual(['Alpha'])
  })
})

describe('knowledgeBasesInFolder', () => {
  const folderById = new Map([['f-1', makeFolder('f-1')]])

  it('selects bases placed in the open folder', () => {
    const bases = [makeBase('kb-root'), makeBase('kb-foldered', { folderId: 'f-1' })]
    const atRoot = knowledgeBasesInFolder(bases, {
      currentFolderId: null,
      folderById,
      foldersResolved: true,
    })
    expect(atRoot.map((kb) => kb.id)).toEqual(['kb-root'])
  })

  it('falls an orphaned base back to the root once the folder index is resolved', () => {
    const bases = [makeBase('kb-orphan', { folderId: 'f-gone' })]
    const resolved = knowledgeBasesInFolder(bases, {
      currentFolderId: null,
      folderById,
      foldersResolved: true,
    })
    expect(resolved.map((kb) => kb.id)).toEqual(['kb-orphan'])
  })

  it('keeps an orphaned base out of every view while the folder index is still loading', () => {
    const bases = [makeBase('kb-orphan', { folderId: 'f-gone' })]
    const loading = knowledgeBasesInFolder(bases, {
      currentFolderId: null,
      folderById,
      foldersResolved: false,
    })
    expect(loading).toEqual([])
  })
})

describe('applyKnowledgeBaseFilters', () => {
  it('passes everything with empty facets', () => {
    const bases = [makeBase('kb-1'), makeBase('kb-2')]
    expect(applyKnowledgeBaseFilters(bases, NO_FILTERS)).toEqual(bases)
  })

  it('filters by connector presence', () => {
    const bases = [
      makeBase('connected', { connectorTypes: ['google-drive'] }),
      makeBase('plain'),
    ]
    expect(
      applyKnowledgeBaseFilters(bases, { ...NO_FILTERS, connector: ['connected'] }).map((kb) => kb.id)
    ).toEqual(['connected'])
    expect(
      applyKnowledgeBaseFilters(bases, { ...NO_FILTERS, connector: ['unconnected'] }).map((kb) => kb.id)
    ).toEqual(['plain'])
  })

  it('filters by document presence', () => {
    const bases = [makeBase('with-docs', { docCount: 3 }), makeBase('empty', { docCount: 0 })]
    expect(
      applyKnowledgeBaseFilters(bases, { ...NO_FILTERS, content: ['has-docs'] }).map((kb) => kb.id)
    ).toEqual(['with-docs'])
    expect(
      applyKnowledgeBaseFilters(bases, { ...NO_FILTERS, content: ['empty'] }).map((kb) => kb.id)
    ).toEqual(['empty'])
  })

  it('combines facets with AND', () => {
    const bases = [
      makeBase('both', { connectorTypes: ['notion'], docCount: 1 }),
      makeBase('connector-only', { connectorTypes: ['notion'], docCount: 0 }),
    ]
    expect(
      applyKnowledgeBaseFilters(bases, {
        ...NO_FILTERS,
        connector: ['connected'],
        content: ['has-docs'],
      }).map((kb) => kb.id)
    ).toEqual(['both'])
  })

  it('filters by owner', () => {
    const bases = [makeBase('mine', { userId: 'u-1' }), makeBase('theirs', { userId: 'u-2' })]
    expect(
      applyKnowledgeBaseFilters(bases, { ...NO_FILTERS, owner: ['u-1'] }).map((kb) => kb.id)
    ).toEqual(['mine'])
  })
})

describe('decorateKnowledgeListItems', () => {
  const memberNameById = new Map([['u-1', 'Alice'], ['u-2', 'Bob']])
  const folder = makeFolder('f-1', null, { name: 'Folder', userId: 'u-2' })
  const base = makeBase('kb-1', {
    name: 'Base',
    userId: 'u-1',
    docCount: 5,
    tokenCount: 100,
    connectorTypes: ['notion'],
  })
  const shared = {
    folders: [folder],
    bases: [base],
    pinnedFolderIds: new Set<string>(),
    pinnedBaseIds: new Set(['kb-1']),
    memberNameById,
  }

  it('marks folder count columns as null keys so folders land last', () => {
    for (const sortColumn of ['documents', 'tokens', 'connectors'] as const) {
      const entries = decorateKnowledgeListItems({ ...shared, sortColumn })
      expect(entries[0].key).toBeNull()
      expect(entries[1].key).toBe(
        sortColumn === 'documents' ? 5 : sortColumn === 'tokens' ? 100 : 1
      )
    }
  })

  it('uses timestamps for created/updated and member names for owner', () => {
    const created = decorateKnowledgeListItems({ ...shared, sortColumn: 'created' })
    expect(created[0].key).toBe(new Date('2026-01-01T00:00:00.000Z').getTime())
    const owner = decorateKnowledgeListItems({ ...shared, sortColumn: 'owner' })
    expect(owner[0].key).toBe('Bob')
    expect(owner[1].key).toBe('Alice')
  })

  it('defaults to the name and carries the pinned flags', () => {
    const entries = decorateKnowledgeListItems({ ...shared, sortColumn: 'name' })
    expect(entries.map((entry) => entry.name)).toEqual(['Folder', 'Base'])
    expect(entries.map((entry) => entry.pinned)).toEqual([false, true])
  })
})
