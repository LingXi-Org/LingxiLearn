import { createLogger } from '@sim/logger'
import { generateId } from '@sim/utils/id'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { requestJson } from '@/lib/api/client/request'
import {
  createFolderContract,
  deleteFolderContract,
  duplicateFolderContract,
  listFoldersContract,
  reorderFoldersContract,
  restoreFolderContract,
  type ServedFolderResourceType,
  updateFolderContract,
} from '@/lib/api/contracts'
import { api, type WorkspaceFolderItem } from '@/lib/lingxi/api'
import { LINGXI_WORKSPACE_ID } from '@/lib/lingxi/capabilities'
import { getFolderMap } from '@/hooks/queries/utils/folder-cache'
import {
  FOLDER_LIST_STALE_TIME,
  type FolderQueryScope,
  folderKeys,
  mapFolder,
} from '@/hooks/queries/utils/folder-keys'
import { invalidateWorkflowLists } from '@/hooks/queries/utils/invalidate-workflow-lists'
import { knowledgeKeys } from '@/hooks/queries/utils/knowledge-keys'
import {
  createOptimisticMutationHandlers,
  generateTempId,
} from '@/hooks/queries/utils/optimistic-mutation'
import { tableKeys } from '@/hooks/queries/utils/table-keys'
import { getTopInsertionSortOrder } from '@/hooks/queries/utils/top-insertion-sort-order'
import { getWorkflows } from '@/hooks/queries/utils/workflow-cache'
import type { WorkspaceFolder } from '@/stores/folders/types'

const logger = createLogger('FolderQueries')

function mapLingxiFolder(
  folder: WorkspaceFolderItem,
  index: number,
  resourceType: ServedFolderResourceType
): WorkspaceFolder {
  const createdAt = folder.createdAt ? new Date(folder.createdAt) : new Date(0)
  const updatedAt = folder.updatedAt ? new Date(folder.updatedAt) : createdAt
  return {
    id: folder.id,
    // The Lingxi native folder endpoint is the canonical file-folder store.
    // Keep the Sim folder shape so the reused resource picker can render it.
    resourceType,
    name: folder.name,
    userId: LINGXI_WORKSPACE_ID,
    workspaceId: LINGXI_WORKSPACE_ID,
    parentId: folder.parentId ?? null,
    locked: false,
    sortOrder: folder.sortOrder ?? index,
    createdAt,
    updatedAt,
    deletedAt: folder.deletedAt ? new Date(folder.deletedAt) : null,
  }
}

async function fetchFolders(
  workspaceId: string,
  scope: FolderQueryScope = 'active',
  resourceType: ServedFolderResourceType = 'workflow',
  signal?: AbortSignal
): Promise<WorkspaceFolder[]> {
  if (workspaceId === LINGXI_WORKSPACE_ID) {
    const { folders } = await api.workspaceFolders(scope)
    return folders.map((folder, index) => mapLingxiFolder(folder, index, resourceType))
  }
  const { folders } = await requestJson(listFoldersContract, {
    query: { workspaceId, scope, resourceType },
    signal,
  })
  return folders.map(mapFolder)
}

export function useFolders(
  workspaceId?: string,
  options?: {
    scope?: FolderQueryScope
    enabled?: boolean
    resourceType?: ServedFolderResourceType
  }
) {
  const scope = options?.scope ?? 'active'
  const resourceType = options?.resourceType ?? 'workflow'
  return useQuery({
    queryKey: folderKeys.list(workspaceId, scope, resourceType),
    queryFn: ({ signal }) => fetchFolders(workspaceId as string, scope, resourceType, signal),
    enabled: Boolean(workspaceId) && (options?.enabled ?? true),
    placeholderData: keepPreviousData,
    staleTime: FOLDER_LIST_STALE_TIME,
  })
}

const selectFolderMap = (folders: WorkspaceFolder[]): Record<string, WorkspaceFolder> =>
  Object.fromEntries(folders.map((folder) => [folder.id, folder]))

export function useFolderMap(
  workspaceId?: string,
  resourceType: ServedFolderResourceType = 'workflow'
) {
  return useQuery({
    queryKey: folderKeys.list(workspaceId, 'active', resourceType),
    queryFn: ({ signal }) => fetchFolders(workspaceId as string, 'active', resourceType, signal),
    enabled: Boolean(workspaceId),
    placeholderData: keepPreviousData,
    staleTime: FOLDER_LIST_STALE_TIME,
    select: selectFolderMap,
  })
}

interface CreateFolderVariables {
  workspaceId: string
  resourceType?: ServedFolderResourceType
  name: string
  parentId?: string
  sortOrder?: number
  id?: string
}

interface UpdateFolderVariables {
  workspaceId: string
  resourceType?: ServedFolderResourceType
  id: string
  updates: Partial<Pick<WorkspaceFolder, 'name' | 'parentId' | 'sortOrder' | 'locked'>>
}

interface DeleteFolderVariables {
  workspaceId: string
  resourceType?: ServedFolderResourceType
  id: string
}

interface DuplicateFolderVariables {
  workspaceId: string
  id: string
  name: string
  parentId?: string | null
  newId?: string
}

/**
 * Refreshes the lists that a folder delete/restore cascade rewrote.
 *
 * The cascade archives or restores the resources inside the folder subtree, so
 * the folder tree alone going stale is not enough — the resource list that
 * renders those rows has to refetch too. Each resource type owns a different
 * cache, hence the switch; a type with no list surface yet is a no-op.
 */
function invalidateCascadedResourceLists(
  queryClient: ReturnType<typeof useQueryClient>,
  resourceType: ServedFolderResourceType,
  workspaceId: string
): Promise<void> | void {
  switch (resourceType) {
    case 'workflow':
      return invalidateWorkflowLists(queryClient, workspaceId, ['active', 'archived'])
    case 'table':
      return queryClient.invalidateQueries({ queryKey: tableKeys.lists() })
    case 'knowledge_base':
      return queryClient.invalidateQueries({ queryKey: knowledgeKeys.lists() })
    /**
     * `file` has no case, and cannot reach here: `servedFolderResourceTypeSchema` does not
     * serve it. Files reads and writes its folders through
     * `/api/workspaces/[id]/files/folders/**`, which owns its own invalidation.
     */
    default:
      return
  }
}

/**
 * Creates optimistic mutation handlers for folder operations
 */
function createFolderMutationHandlers<
  TVariables extends { workspaceId: string; resourceType?: ServedFolderResourceType },
>(
  queryClient: ReturnType<typeof useQueryClient>,
  name: string,
  createOptimisticFolder: (
    variables: TVariables,
    tempId: string,
    previousFolders: Record<string, WorkspaceFolder>
  ) => WorkspaceFolder,
  customGenerateTempId?: (variables: TVariables) => string
) {
  return createOptimisticMutationHandlers<WorkspaceFolder, TVariables, WorkspaceFolder>(
    queryClient,
    {
      name,
      getQueryKey: (variables) =>
        folderKeys.list(variables.workspaceId, 'active', variables.resourceType ?? 'workflow'),
      getSnapshot: (variables) => ({
        ...getFolderMap(variables.workspaceId, variables.resourceType ?? 'workflow'),
      }),
      generateTempId: customGenerateTempId ?? (() => generateTempId('temp-folder')),
      createOptimisticItem: (variables, tempId) => {
        const previousFolders = getFolderMap(
          variables.workspaceId,
          variables.resourceType ?? 'workflow'
        )
        return createOptimisticFolder(variables, tempId, previousFolders)
      },
      applyOptimisticUpdate: (tempId, item) => {
        queryClient.setQueryData<WorkspaceFolder[]>(
          folderKeys.list(item.workspaceId, 'active', item.resourceType),
          (old) => [...(old ?? []), item]
        )
      },
      replaceOptimisticEntry: (tempId, data) => {
        queryClient.setQueryData<WorkspaceFolder[]>(
          folderKeys.list(data.workspaceId, 'active', data.resourceType),
          (old) => (old ?? []).map((folder) => (folder.id === tempId ? data : folder))
        )
      },
      rollback: (snapshot, variables) => {
        queryClient.setQueryData(
          folderKeys.list(variables.workspaceId, 'active', variables.resourceType ?? 'workflow'),
          Object.values(snapshot)
        )
      },
    }
  )
}

export function useCreateFolder() {
  const queryClient = useQueryClient()

  const handlers = createFolderMutationHandlers<CreateFolderVariables>(
    queryClient,
    'CreateFolder',
    (variables, tempId, previousFolders) => {
      const resourceType = variables.resourceType ?? 'workflow'
      /**
       * Only the workflow tree interleaves folders and resources in one user-ordered list, so
       * only it derives the optimistic placement from the workflows too. The other trees are
       * ordered by the folder rows alone — mirroring `nextFolderSortOrder`, which consults a
       * resource's sort column only when the config declares one. Feeding workflow sort orders
       * into a knowledge-base or table folder would place it against an unrelated ordering
       * space and flicker until the server response replaced it.
       */
      const currentWorkflows =
        resourceType === 'workflow'
          ? Object.fromEntries(getWorkflows(variables.workspaceId).map((w) => [w.id, w]))
          : {}

      return {
        id: tempId,
        name: variables.name,
        userId: '',
        workspaceId: variables.workspaceId,
        parentId: variables.parentId || null,
        resourceType,
        locked: false,
        sortOrder:
          variables.sortOrder ??
          getTopInsertionSortOrder(
            currentWorkflows,
            previousFolders,
            variables.workspaceId,
            variables.parentId
          ),
        createdAt: new Date(),
        updatedAt: new Date(),
        deletedAt: null,
      }
    },
    (variables) => variables.id ?? generateId()
  )

  return useMutation({
    mutationFn: async ({
      workspaceId,
      sortOrder,
      resourceType = 'workflow',
      ...payload
    }: CreateFolderVariables) => {
      if (workspaceId === LINGXI_WORKSPACE_ID) {
        const { folder } = await api.createWorkspaceFolder(payload.name, payload.parentId ?? null)
        return mapLingxiFolder(folder, sortOrder ?? 0, resourceType)
      }
      const { folder } = await requestJson(createFolderContract, {
        body: { ...payload, workspaceId, sortOrder, resourceType },
      })
      return mapFolder(folder)
    },
    ...handlers,
  })
}

export function useUpdateFolder() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      workspaceId,
      resourceType = 'workflow',
      id,
      updates,
    }: UpdateFolderVariables) => {
      if (workspaceId === LINGXI_WORKSPACE_ID) {
        const body = {
          ...(updates.name !== undefined ? { name: updates.name } : {}),
          ...(updates.parentId !== undefined ? { parentId: updates.parentId } : {}),
        }
        const { folder } = await api.updateWorkspaceFolder(id, body)
        return mapLingxiFolder(folder, updates.sortOrder ?? 0, resourceType)
      }
      const { folder } = await requestJson(updateFolderContract, {
        params: { id },
        query: { resourceType },
        body: updates,
      })
      return mapFolder(folder)
    },
    onSettled: (_data, _error, variables) => {
      queryClient.invalidateQueries({
        queryKey: folderKeys.resource(variables.resourceType ?? 'workflow'),
      })
    },
  })
}

export function useDeleteFolderMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ workspaceId, resourceType = 'workflow', id }: DeleteFolderVariables) => {
      if (workspaceId === LINGXI_WORKSPACE_ID) {
        return api.archiveWorkspaceFolder(id)
      }
      return requestJson(deleteFolderContract, { params: { id }, query: { resourceType } })
    },
    onSettled: (_data, _error, variables) => {
      const resourceType = variables.resourceType ?? 'workflow'
      queryClient.invalidateQueries({ queryKey: folderKeys.resource(resourceType) })
      return invalidateCascadedResourceLists(queryClient, resourceType, variables.workspaceId)
    },
  })
}

interface RestoreFolderVariables {
  workspaceId: string
  resourceType?: ServedFolderResourceType
  folderId: string
}

export function useRestoreFolder() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      workspaceId,
      resourceType = 'workflow',
      folderId,
    }: RestoreFolderVariables) => {
      if (workspaceId === LINGXI_WORKSPACE_ID) {
        return api.restoreWorkspaceFolder(folderId)
      }
      return requestJson(restoreFolderContract, {
        params: { id: folderId },
        body: { workspaceId, resourceType },
      })
    },
    onSettled: (_data, _error, variables) => {
      const resourceType = variables.resourceType ?? 'workflow'
      queryClient.invalidateQueries({ queryKey: folderKeys.resource(resourceType) })
      return invalidateCascadedResourceLists(queryClient, resourceType, variables.workspaceId)
    },
  })
}

/**
 * Workflow-only by design, unlike the other folder mutations in this file: duplication copies
 * the workflows inside the folder, and `POST /api/folders/[id]/duplicate` has no equivalent
 * for knowledge bases or tables. The `resourceType: 'workflow'` below is that constraint, not
 * an oversight — generalizing it would optimistically insert a folder the route then refuses.
 */
export function useDuplicateFolderMutation() {
  const queryClient = useQueryClient()

  const handlers = createFolderMutationHandlers<DuplicateFolderVariables>(
    queryClient,
    'DuplicateFolder',
    (variables, tempId, previousFolders) => {
      const currentWorkflows = Object.fromEntries(
        getWorkflows(variables.workspaceId).map((w) => [w.id, w])
      )

      const sourceFolder = previousFolders[variables.id]
      const targetParentId = variables.parentId ?? sourceFolder?.parentId ?? null
      return {
        id: tempId,
        name: variables.name,
        userId: sourceFolder?.userId || '',
        workspaceId: variables.workspaceId,
        parentId: targetParentId,
        resourceType: 'workflow' as const,
        locked: false,
        sortOrder: getTopInsertionSortOrder(
          currentWorkflows,
          previousFolders,
          variables.workspaceId,
          targetParentId
        ),
        createdAt: new Date(),
        updatedAt: new Date(),
        deletedAt: null,
      }
    },
    (variables) => variables.newId ?? generateId()
  )

  return useMutation({
    mutationFn: async ({
      id,
      workspaceId,
      name,
      parentId,
      newId,
    }: DuplicateFolderVariables): Promise<WorkspaceFolder> => {
      if (workspaceId === LINGXI_WORKSPACE_ID) {
        const { folder } = await api.createWorkspaceFolder(name, parentId ?? null)
        return mapLingxiFolder(folder, 0, 'workflow')
      }
      const { folder } = await requestJson(duplicateFolderContract, {
        params: { id },
        body: {
          workspaceId,
          name,
          parentId: parentId ?? null,
          newId,
        },
      })
      return mapFolder(folder)
    },
    ...handlers,
    onSettled: (_data, _error, variables) => {
      queryClient.invalidateQueries({ queryKey: folderKeys.list(variables.workspaceId) })
      return invalidateWorkflowLists(queryClient, variables.workspaceId)
    },
  })
}

interface ReorderFoldersVariables {
  workspaceId: string
  resourceType?: ServedFolderResourceType
  updates: Array<{
    id: string
    sortOrder: number
    parentId?: string | null
  }>
}

export function useReorderFolders() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      resourceType = 'workflow',
      ...variables
    }: ReorderFoldersVariables): Promise<void> => {
      if (variables.workspaceId === LINGXI_WORKSPACE_ID) {
        await Promise.all(
          variables.updates.map((update) =>
            api.updateWorkspaceFolder(update.id, {
              ...(update.parentId !== undefined ? { parentId: update.parentId } : {}),
            })
          )
        )
        return
      }
      await requestJson(reorderFoldersContract, { body: { ...variables, resourceType } })
    },
    onMutate: async (variables) => {
      const listKey = folderKeys.list(
        variables.workspaceId,
        'active',
        variables.resourceType ?? 'workflow'
      )
      await queryClient.cancelQueries({ queryKey: listKey })

      const snapshot = queryClient.getQueryData<WorkspaceFolder[]>(listKey)

      const updatesById = new Map(variables.updates.map((update) => [update.id, update]))
      queryClient.setQueryData<WorkspaceFolder[]>(listKey, (old) => {
        if (!old?.length) return old
        return old.map((folder) => {
          const update = updatesById.get(folder.id)
          if (!update) return folder
          return {
            ...folder,
            sortOrder: update.sortOrder,
            parentId: update.parentId !== undefined ? update.parentId : folder.parentId,
          }
        })
      })

      return { snapshot }
    },
    onError: (_error, variables, context) => {
      if (context?.snapshot) {
        queryClient.setQueryData(
          folderKeys.list(variables.workspaceId, 'active', variables.resourceType ?? 'workflow'),
          context.snapshot
        )
      }
    },
    onSettled: (_data, _error, variables) => {
      queryClient.invalidateQueries({
        queryKey: folderKeys.list(
          variables.workspaceId,
          'active',
          variables.resourceType ?? 'workflow'
        ),
      })
    },
  })
}
