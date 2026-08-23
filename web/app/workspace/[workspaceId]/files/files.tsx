'use client'

import { useCallback, useEffect, useMemo, useRef } from 'react'
import { Loader } from '@/components/ui-kit'
import { useParams, useRouter } from 'next/navigation'
import { useQueryStates } from 'nuqs'
import type { WorkspaceFileRecord } from '@/lib/uploads/contexts/workspace'
import type { BreadcrumbItem } from '@/app/workspace/[workspaceId]/components'
import { Resource } from '@/app/workspace/[workspaceId]/components'
import {
  breadcrumbFolderChain,
  FOLDERED_RESOURCE_HEADERS,
  folderBreadcrumbItems,
  folderedResourceListHref,
} from '@/app/workspace/[workspaceId]/components/folders'
import { ShareModalHost } from '@/app/workspace/[workspaceId]/files/components/share-modal-host'
import { FileDetail } from '@/app/workspace/[workspaceId]/files/file-detail'
import { FilesList } from '@/app/workspace/[workspaceId]/files/files-list'
import { useFilesData } from '@/app/workspace/[workspaceId]/files/hooks/use-files-data'
import { useWorkspaceFilesRoom } from '@/app/workspace/[workspaceId]/files/hooks/use-workspace-files-room'
import { filesParsers, filesUrlKeys } from '@/app/workspace/[workspaceId]/files/search-params'
import { useUserPermissionsContext } from '@/app/workspace/[workspaceId]/providers/workspace-permissions-provider'
import { usePermissionConfig } from '@/hooks/use-permission-config'

const FILES_HEADER = FOLDERED_RESOURCE_HEADERS.file

/**
 * The Files feature shell: route params, permission gating, the live files room, and the
 * shared query bundle — then routes between the loading shell, the file detail view, and the
 * list view. All CRUD, filtering/sorting, and viewer details live in `files-list.tsx`,
 * `file-detail.tsx`, the `files/hooks` controllers, and the `files/lib` domain layer.
 */
export function Files() {
  const params = useParams()
  const router = useRouter()
  const [{ folderId: currentFolderId, new: isNewFile, shareFileId }, setFilesParams] =
    useQueryStates(filesParsers, filesUrlKeys)
  const workspaceId = params?.workspaceId as string

  const fileIdFromRoute =
    typeof params?.fileId === 'string' && params.fileId.length > 0 ? params.fileId : null
  const userPermissions = useUserPermissionsContext()
  const canEdit = userPermissions.canEdit === true
  const { config: permissionConfig } = usePermissionConfig()

  // Joined for the live file tree: a `workspace-files-changed` broadcast invalidates the
  // browser. "Who's in this file" comes from the file-doc room (see FileDocRoomProvider),
  // not from who's browsing the Files section.
  useWorkspaceFilesRoom(workspaceId)

  useEffect(() => {
    if (permissionConfig.hideFilesTab) {
      router.replace(`/workspace/${workspaceId}`)
    }
  }, [permissionConfig.hideFilesTab, router, workspaceId])

  const data = useFilesData(workspaceId)
  const { files, isLoading, folderById } = data

  const filesRef = useRef(files)
  filesRef.current = files

  const selectedFile = useMemo(
    () => (fileIdFromRoute ? files.find((f) => f.id === fileIdFromRoute) : null),
    [fileIdFromRoute, files]
  )

  // The `new` flag is one-shot: strip it once the route has consumed it so a reload or a
  // back-nav does not reopen compose mode.
  useEffect(() => {
    if (isNewFile && fileIdFromRoute) {
      void setFilesParams({ new: null }, { history: 'replace', scroll: false })
    }
  }, [isNewFile, fileIdFromRoute, setFilesParams])

  const handleNavigateListFolder = useCallback(
    (folderId: string | null) => {
      void setFilesParams({ folderId, new: null })
    },
    [setFilesParams]
  )

  const handleOpenFile = useCallback(
    (file: WorkspaceFileRecord) => {
      router.push(
        file.folderId
          ? `/workspace/${workspaceId}/files/${file.id}?folderId=${file.folderId}`
          : `/workspace/${workspaceId}/files/${file.id}`
      )
    },
    [router, workspaceId]
  )

  const handleShareFile = useCallback(
    (fileId: string) => {
      setFilesParams({ shareFileId: fileId }, { history: 'replace' })
    },
    [setFilesParams]
  )

  const handleCloseShare = useCallback(() => {
    setFilesParams({ shareFileId: null }, { history: 'replace' })
  }, [setFilesParams])

  if (fileIdFromRoute && !selectedFile && isLoading) {
    /**
     * The trail while a file's content loads. Holds the URL's open folder so arriving from a
     * list page inside `A/B` doesn't collapse to `Files / …` and jump back out once the file
     * lands; a cold deep-link has no `?folderId=` and no loaded file, so it starts at the root.
     */
    const loadingBreadcrumbs: BreadcrumbItem[] = folderBreadcrumbItems({
      rootLabel: FILES_HEADER.rootLabel,
      rootIcon: FILES_HEADER.rootIcon,
      breadcrumbs: breadcrumbFolderChain(currentFolderId, folderById),
      onNavigate: (folderId) =>
        router.push(folderedResourceListHref('file', workspaceId, folderId)),
      trailing: [{ label: '…', terminal: true }],
    })

    return (
      <Resource>
        <Resource.Header icon={FILES_HEADER.rootIcon} breadcrumbs={loadingBreadcrumbs} />
        <div className='flex flex-1 items-center justify-center bg-[var(--bg)]'>
          <Loader className='size-[20px] text-[var(--text-secondary)]' animate />
        </div>
      </Resource>
    )
  }

  if (selectedFile) {
    return (
      <>
        <FileDetail
          workspaceId={workspaceId}
          file={selectedFile}
          isNewFile={isNewFile}
          canEdit={canEdit}
          currentFolderId={currentFolderId}
          filesRef={filesRef}
          folderById={folderById}
          onShareFile={handleShareFile}
        />
        <ShareModalHost
          workspaceId={workspaceId}
          files={files}
          shareFileId={shareFileId}
          onClose={handleCloseShare}
        />
      </>
    )
  }

  return (
    <>
      <FilesList
        workspaceId={workspaceId}
        canEdit={canEdit}
        permissionsLoading={userPermissions.isLoading}
        data={data}
        currentFolderId={currentFolderId}
        onNavigateListFolder={handleNavigateListFolder}
        onOpenFile={handleOpenFile}
        onShareFile={handleShareFile}
      />
      <ShareModalHost
        workspaceId={workspaceId}
        files={files}
        shareFileId={shareFileId}
        onClose={handleCloseShare}
      />
    </>
  )
}
