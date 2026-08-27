'use client'

import { memo, useEffect, useMemo, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button, Skeleton, Tooltip } from '@/components/ui-kit'
import {
  Download,
  FileX,
  Folder as FolderIcon,
  Library,
  SquareArrowUpRight,
} from '@/components/ui-kit/icons'
import { isApiClientError } from '@/lib/api/client/errors'
import type { FilePreviewSession } from '@/lib/copilot/request/session'
import { tryCanonicalWorkspaceFilePath } from '@/lib/copilot/vfs/path-utils'
import { LingxiArtifactResource } from '@/lib/lingxi/components/lingxi-artifact-resource'
import { LingxiRuntimeGraph } from '@/lib/lingxi/components/lingxi-runtime-graph'
import { createLogger } from '@/lib/logger'
import { triggerFileDownload } from '@/lib/uploads/client/download'
import { getFileExtension, getMimeTypeFromExtension } from '@/lib/uploads/utils/file-utils'
import type { WorkflowsEditorRuntime } from '@/app/(landing)/workflows/components/workflows-editor-loop'
import { WorkflowsEditorLoop } from '@/app/(landing)/workflows/components/workflows-editor-loop'
import {
  FileViewer,
  type PreviewMode,
  resolveFileCategory,
} from '@/app/workspace/[workspaceId]/files/components/file-viewer'
import type { BrowserPanelOverlayController } from '@/app/workspace/[workspaceId]/home/components/mothership-view/components/resource-content/components/browser-session/browser-panel-occlusion'
import { BrowserSession } from '@/app/workspace/[workspaceId]/home/components/mothership-view/components/resource-content/components/browser-session/browser-session'
import { GenericResourceContent } from '@/app/workspace/[workspaceId]/home/components/mothership-view/components/resource-content/components/generic-resource-content'
import { TerminalSession } from '@/app/workspace/[workspaceId]/home/components/mothership-view/components/resource-content/components/terminal-session/terminal-session'
import {
  RESOURCE_TAB_ICON_BUTTON_CLASS,
  RESOURCE_TAB_ICON_CLASS,
} from '@/app/workspace/[workspaceId]/home/components/mothership-view/components/resource-tabs/resource-tab-controls'
import { hasRenderableFilePreviewContent } from '@/app/workspace/[workspaceId]/home/hooks/preview'
import type {
  GenericResourceData,
  MothershipResource,
} from '@/app/workspace/[workspaceId]/home/types'
import { KnowledgeBase } from '@/app/workspace/[workspaceId]/knowledge/[id]/base'
import { LogDetailsContent } from '@/app/workspace/[workspaceId]/logs/components'
import { mapExecutionLogDetail } from '@/app/workspace/[workspaceId]/logs/model/execution-log-mapper'
import { useUserPermissionsContext } from '@/app/workspace/[workspaceId]/providers/workspace-permissions-provider'
import { Table } from '@/app/workspace/[workspaceId]/tables/[tableId]/table'
import { useFolders } from '@/hooks/queries/folders'
import { useLogDetail } from '@/hooks/queries/logs'
import { exportTable } from '@/hooks/queries/tables'
import { useWorkspaceFiles } from '@/hooks/queries/workspace-files'

const LOADING_SKELETON = (
  <div className='flex h-full flex-col gap-2 p-6'>
    <Skeleton className='h-[16px] w-[60%]' />
    <Skeleton className='h-[16px] w-[80%]' />
    <Skeleton className='h-[16px] w-[40%]' />
  </div>
)

interface ResourceContentProps {
  workspaceId: string
  desktopScopeId: string
  resource: MothershipResource
  previewMode?: PreviewMode
  previewSession?: FilePreviewSession | null
  isAgentResponding?: boolean
  genericResourceData?: GenericResourceData
  lingxiRuntime?: WorkflowsEditorRuntime
  previewContextKey?: string
  /** Resolved server-side by the home page — the embedded table can't read
   *  AppConfig itself, so the flag is threaded down rather than looked up. */
  tableViewsEnabled?: boolean
  onNotFound?: (resourceId: string) => void
  /**
   * Whether this resource is the one on screen. Only the persistent panels
   * (browser, terminal) read it — to stand down document-wide observers while
   * hidden — so it defaults to visible for every other resource, which is only
   * ever rendered when active.
   */
  visible?: boolean
  /** Registers the active browser's targeted renderer-overlay handshake. */
  onBrowserOverlayControllerChange?: (controller: BrowserPanelOverlayController | null) => void
}

/**
 * Renders the content for the currently active mothership resource.
 * Handles table, file, and workflow resource types with appropriate
 * embedded rendering for each.
 */
const STREAMING_EPOCH = new Date(0)

/**
 * Grace window kept locked after the agent stops streaming into the file, so the lock bridges the
 * gaps between the file subagent's sequential edit sections instead of flickering open between them.
 */
const AGENT_EDIT_LOCK_GRACE_MS = 1500

/**
 * Holds the editor read-only while the agent is actively writing to the file, plus a short grace so
 * brief gaps between edit sections don't unlock it. Releases as soon as the turn ends
 * (`isAgentResponding` false) so the file becomes editable the moment the agent is done, even when
 * the surrounding turn keeps running — the completed preview session otherwise lingers all turn.
 */
function useAgentFileEditLock(isStreamingToFile: boolean, isAgentResponding: boolean): boolean {
  const [locked, setLocked] = useState(isStreamingToFile)
  const graceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (graceTimerRef.current !== null) {
      clearTimeout(graceTimerRef.current)
      graceTimerRef.current = null
    }
    if (isStreamingToFile) {
      setLocked(true)
      return
    }
    if (!isAgentResponding) {
      setLocked(false)
      return
    }
    graceTimerRef.current = setTimeout(() => {
      graceTimerRef.current = null
      setLocked(false)
    }, AGENT_EDIT_LOCK_GRACE_MS)
    return () => {
      if (graceTimerRef.current !== null) {
        clearTimeout(graceTimerRef.current)
        graceTimerRef.current = null
      }
    }
  }, [isStreamingToFile, isAgentResponding])

  return locked
}

export const ResourceContent = memo(function ResourceContent({
  workspaceId,
  desktopScopeId,
  resource,
  previewMode,
  previewSession,
  isAgentResponding,
  genericResourceData,
  lingxiRuntime,
  previewContextKey,
  tableViewsEnabled,
  onNotFound,
  visible = true,
  onBrowserOverlayControllerChange,
}: ResourceContentProps) {
  const streamFileName = previewSession?.fileName || 'file.md'
  const syntheticFile = useMemo(() => {
    const ext = getFileExtension(streamFileName)
    const SOURCE_MIME_MAP: Record<string, string> = {
      pptx: 'text/x-pptxgenjs',
      docx: 'text/x-docxjs',
      pdf: 'text/x-pdflibjs',
    }
    const type = SOURCE_MIME_MAP[ext] ?? getMimeTypeFromExtension(ext)
    return {
      id: 'streaming-file',
      workspaceId,
      name: streamFileName,
      key: '',
      path: '',
      folderId: null,
      size: 0,
      type,
      uploadedBy: '',
      uploadedAt: STREAMING_EPOCH,
      updatedAt: STREAMING_EPOCH,
    }
  }, [workspaceId, streamFileName])

  const disableStreamingAutoScroll = previewSession?.operation === 'patch'
  // `append`/`patch` stream complete full-file snapshots (built on the existing file), so the editor
  // applies each live. `create`/`update` are streamed from scratch and would collapse an open doc, so
  // the editor holds until settle. See the rich-markdown streaming tick.
  const streamIsIncremental =
    previewSession?.operation === 'append' || previewSession?.operation === 'patch'
  const isTextPreview =
    !!previewSession && resolveFileCategory(null, previewSession.fileName) === 'text-editable'
  // Feed streamed content only while actively streaming. On completion the session keeps
  // `previewText` for history, but clearing it here lets the editor reconcile to the agent's
  // server-side write and hand off to the editable surface (the agent persists, not the editor).
  const textStreamingContent =
    isTextPreview &&
    previewSession?.status === 'streaming' &&
    typeof previewSession?.previewText === 'string' &&
    hasRenderableFilePreviewContent(previewSession)
      ? previewSession.previewText
      : undefined

  const isAgentEditing = useAgentFileEditLock(
    previewSession?.status === 'streaming',
    Boolean(isAgentResponding)
  )

  if (resource.id.startsWith('lingxi-artifact:')) {
    return <LingxiArtifactResource resourceId={resource.id} />
  }

  if (resource.id.startsWith('runtime-graph:')) {
    return (
      <LingxiRuntimeGraph
        taskId={resource.id.split(':')[1] ?? ''}
        executionSnapshot={lingxiRuntime?.executionSnapshot}
        events={lingxiRuntime?.events}
      />
    )
  }

  if (resource.id === 'streaming-file') {
    return (
      <div className='flex h-full flex-col overflow-hidden'>
        <FileViewer
          file={syntheticFile}
          workspaceId={workspaceId}
          canEdit={false}
          previewMode={previewMode ?? 'preview'}
          streamingContent={textStreamingContent}
          isAgentEditing={isAgentEditing}
          streamIsIncremental={streamIsIncremental}
          disableStreamingAutoScroll={disableStreamingAutoScroll}
          previewContextKey={previewContextKey}
        />
      </div>
    )
  }

  switch (resource.type) {
    case 'workflow':
      return lingxiRuntime ? <WorkflowsEditorLoop live runtime={lingxiRuntime} /> : null
    case 'table':
      return (
        <Table
          key={resource.id}
          workspaceId={workspaceId}
          tableId={resource.id}
          embedded
          viewsEnabled={tableViewsEnabled}
        />
      )

    case 'file':
      return (
        <EmbeddedFile
          key={resource.id}
          workspaceId={workspaceId}
          fileId={resource.id}
          filePath={resource.path}
          previewMode={previewMode}
          streamingContent={
            previewSession?.fileId === resource.id ? textStreamingContent : undefined
          }
          isAgentEditing={isAgentEditing}
          streamIsIncremental={streamIsIncremental}
          streamOperation={previewSession?.operation}
          disableStreamingAutoScroll={disableStreamingAutoScroll}
          previewContextKey={previewContextKey}
        />
      )

    case 'knowledgebase':
      return (
        <KnowledgeBase
          key={resource.id}
          id={resource.id}
          knowledgeBaseName={resource.title}
          workspaceId={workspaceId}
        />
      )

    case 'folder':
      return <EmbeddedFolder key={resource.id} workspaceId={workspaceId} folderId={resource.id} />

    case 'log':
      return (
        <EmbeddedLog
          key={resource.id}
          workspaceId={workspaceId}
          logId={resource.id}
          onNotFound={onNotFound ? () => onNotFound(resource.id) : undefined}
        />
      )

    case 'generic':
      return (
        <GenericResourceContent key={resource.id} data={genericResourceData ?? { entries: [] }} />
      )

    case 'browser':
      return (
        <BrowserSession
          key={resource.id}
          scopeId={desktopScopeId}
          visible={visible}
          onOverlayControllerChange={onBrowserOverlayControllerChange}
        />
      )

    case 'terminal':
      return <TerminalSession key={resource.id} scopeId={desktopScopeId} visible={visible} />

    default:
      return null
  }
})

interface ResourceActionsProps {
  workspaceId: string
  resource: MothershipResource
}

export function ResourceActions({ workspaceId, resource }: ResourceActionsProps) {
  switch (resource.type) {
    case 'file':
      return (
        <EmbeddedFileActions
          workspaceId={workspaceId}
          fileId={resource.id}
          filePath={resource.path}
        />
      )
    case 'knowledgebase':
      return (
        <EmbeddedKnowledgeBaseActions workspaceId={workspaceId} knowledgeBaseId={resource.id} />
      )
    case 'table':
      return <EmbeddedTableActions workspaceId={workspaceId} tableId={resource.id} />
    case 'log':
      return <EmbeddedLogActions workspaceId={workspaceId} logId={resource.id} />
    case 'folder':
    case 'generic':
    case 'browser':
    case 'terminal':
      return null
    default:
      return null
  }
}

interface EmbeddedKnowledgeBaseActionsProps {
  workspaceId: string
  knowledgeBaseId: string
}

export function EmbeddedKnowledgeBaseActions({
  workspaceId,
  knowledgeBaseId,
}: EmbeddedKnowledgeBaseActionsProps) {
  const router = useRouter()

  const handleOpenKnowledgeBase = () => {
    router.push(`/workspace/${workspaceId}/knowledge/${knowledgeBaseId}`)
  }

  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <Button
          variant='subtle'
          onClick={handleOpenKnowledgeBase}
          className={RESOURCE_TAB_ICON_BUTTON_CLASS}
          aria-label='Open knowledge base'
        >
          <SquareArrowUpRight className={RESOURCE_TAB_ICON_CLASS} />
        </Button>
      </Tooltip.Trigger>
      <Tooltip.Content side='bottom'>
        <p>Open knowledge base</p>
      </Tooltip.Content>
    </Tooltip.Root>
  )
}

const tableLogger = createLogger('EmbeddedTableActions')

interface EmbeddedTableActionsProps {
  workspaceId: string
  tableId: string
}

function EmbeddedTableActions({ workspaceId, tableId }: EmbeddedTableActionsProps) {
  const router = useRouter()

  const handleOpenTable = () => {
    router.push(`/workspace/${workspaceId}/tables/${tableId}`)
  }

  const handleExport = async () => {
    try {
      await exportTable(workspaceId, tableId)
    } catch (err) {
      tableLogger.error('Failed to export table:', err)
    }
  }

  return (
    <>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <Button
            variant='subtle'
            onClick={handleOpenTable}
            className={RESOURCE_TAB_ICON_BUTTON_CLASS}
            aria-label='Open table'
          >
            <SquareArrowUpRight className={RESOURCE_TAB_ICON_CLASS} />
          </Button>
        </Tooltip.Trigger>
        <Tooltip.Content side='bottom'>
          <p>Open table</p>
        </Tooltip.Content>
      </Tooltip.Root>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <Button
            variant='subtle'
            onClick={() => void handleExport()}
            className={RESOURCE_TAB_ICON_BUTTON_CLASS}
            aria-label='Export table as CSV'
          >
            <Download className={RESOURCE_TAB_ICON_CLASS} />
          </Button>
        </Tooltip.Trigger>
        <Tooltip.Content side='bottom'>
          <p>Export CSV</p>
        </Tooltip.Content>
      </Tooltip.Root>
    </>
  )
}

const fileLogger = createLogger('EmbeddedFileActions')

function matchesWorkspaceFilePath(
  file: { folderPath?: string | null; name: string },
  filePath: string
): boolean {
  return (
    tryCanonicalWorkspaceFilePath({ folderPath: file.folderPath, name: file.name }) === filePath
  )
}

interface EmbeddedFileActionsProps {
  workspaceId: string
  fileId: string
  filePath?: string
}

function EmbeddedFileActions({ workspaceId, fileId, filePath }: EmbeddedFileActionsProps) {
  const router = useRouter()
  const { data: files = [] } = useWorkspaceFiles(workspaceId)
  const file = useMemo(
    () => files.find((f) => f.id === fileId || (filePath && matchesWorkspaceFilePath(f, filePath))),
    [files, fileId, filePath]
  )

  const handleDownload = async () => {
    if (!file) return
    try {
      await triggerFileDownload(file)
    } catch (err) {
      fileLogger.error('Failed to download file:', err)
    }
  }

  const handleOpenInFiles = () => {
    router.push(`/workspace/${workspaceId}/files/${encodeURIComponent(file?.id ?? fileId)}`)
  }

  return (
    <>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <Button
            variant='subtle'
            onClick={handleOpenInFiles}
            className={RESOURCE_TAB_ICON_BUTTON_CLASS}
            aria-label='Open in files'
          >
            <SquareArrowUpRight className={RESOURCE_TAB_ICON_CLASS} />
          </Button>
        </Tooltip.Trigger>
        <Tooltip.Content side='bottom'>
          <p>Open in files</p>
        </Tooltip.Content>
      </Tooltip.Root>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <Button
            variant='subtle'
            onClick={() => void handleDownload()}
            disabled={!file}
            className={RESOURCE_TAB_ICON_BUTTON_CLASS}
            aria-label='Download file'
          >
            <Download className={RESOURCE_TAB_ICON_CLASS} />
          </Button>
        </Tooltip.Trigger>
        <Tooltip.Content side='bottom'>
          <p>Download</p>
        </Tooltip.Content>
      </Tooltip.Root>
    </>
  )
}

interface EmbeddedFileProps {
  workspaceId: string
  fileId: string
  filePath?: string
  previewMode?: PreviewMode
  streamingContent?: string
  isAgentEditing?: boolean
  streamIsIncremental?: boolean
  streamOperation?: string
  disableStreamingAutoScroll?: boolean
  previewContextKey?: string
}

function EmbeddedFile({
  workspaceId,
  fileId,
  filePath,
  previewMode,
  streamingContent,
  isAgentEditing,
  streamIsIncremental,
  streamOperation,
  disableStreamingAutoScroll = false,
  previewContextKey,
}: EmbeddedFileProps) {
  const { canEdit } = useUserPermissionsContext()
  const { data: files = [], isLoading, isFetching } = useWorkspaceFiles(workspaceId)
  const file = useMemo(
    () => files.find((f) => f.id === fileId || (filePath && matchesWorkspaceFilePath(f, filePath))),
    [files, fileId, filePath]
  )

  if (isLoading || (isFetching && !file)) return LOADING_SKELETON

  if (!file) {
    return (
      <div className='flex h-full flex-col items-center justify-center gap-3'>
        <FileX className='size-[32px] text-[var(--text-icon)]' />
        <div className='flex flex-col items-center gap-1'>
          <h2 className='text-[20px] text-[var(--text-primary)]'>File not found</h2>
          <p className='text-[var(--text-body)] text-small'>
            This file may have been deleted or moved
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className='flex h-full flex-col overflow-hidden'>
      <FileViewer
        key={file.id}
        file={file}
        workspaceId={workspaceId}
        canEdit={canEdit}
        previewMode={previewMode}
        streamingContent={streamingContent}
        isAgentEditing={isAgentEditing}
        streamIsIncremental={streamIsIncremental}
        streamOperation={streamOperation}
        disableStreamingAutoScroll={disableStreamingAutoScroll}
        previewContextKey={previewContextKey}
        collaborative
      />
    </div>
  )
}

interface EmbeddedFolderProps {
  workspaceId: string
  folderId: string
}

function EmbeddedFolder({ workspaceId, folderId }: EmbeddedFolderProps) {
  const { data: folderList, isPending: isFoldersPending } = useFolders(workspaceId)

  const folder = (folderList ?? []).find((f) => f.id === folderId)

  if (isFoldersPending) return LOADING_SKELETON

  if (!folder) {
    return (
      <div className='flex h-full flex-col items-center justify-center gap-3'>
        <FolderIcon className='size-[32px] text-[var(--text-icon)]' />
        <div className='flex flex-col items-center gap-1'>
          <h2 className='text-[20px] text-[var(--text-primary)]'>Folder not found</h2>
          <p className='text-[var(--text-body)] text-small'>
            This folder may have been deleted or moved
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className='flex h-full flex-col overflow-y-auto p-6'>
      <h2 className='mb-4 text-[16px] text-[var(--text-primary)]'>{folder.name}</h2>
      <p className='text-[13px] text-[var(--text-muted)]'>
        This folder contains no editable resources.
      </p>
    </div>
  )
}

interface EmbeddedLogProps {
  workspaceId: string
  logId: string
  onNotFound?: () => void
}

function EmbeddedLog({ workspaceId, logId, onNotFound }: EmbeddedLogProps) {
  const { data: log, isLoading, error } = useLogDetail(logId, workspaceId)

  const onNotFoundRef = useRef(onNotFound)
  onNotFoundRef.current = onNotFound

  useEffect(() => {
    if (isApiClientError(error) && error.status === 404) {
      onNotFoundRef.current?.()
    }
  }, [error])

  if (isLoading) return LOADING_SKELETON

  if (!log) {
    return (
      <div className='flex h-full flex-col items-center justify-center gap-3'>
        <Library className='size-[32px] text-[var(--text-icon)]' />
        <div className='flex flex-col items-center gap-1'>
          <h2 className='text-[20px] text-[var(--text-primary)]'>Log not found</h2>
          <p className='text-[var(--text-body)] text-small'>
            This log may have been deleted or is no longer available
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className='flex h-full flex-col overflow-hidden px-3.5 pt-3'>
      <LogDetailsContent log={mapExecutionLogDetail(log)} />
    </div>
  )
}

interface EmbeddedLogActionsProps {
  workspaceId: string
  logId: string
}

export function EmbeddedLogActions({ workspaceId, logId }: EmbeddedLogActionsProps) {
  const router = useRouter()
  const { data: log } = useLogDetail(logId, workspaceId)

  const handleOpenInLogs = () => {
    const param = log?.executionId ? `?executionId=${log.executionId}` : ''
    router.push(`/workspace/${workspaceId}/logs${param}`)
  }

  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <Button
          variant='subtle'
          onClick={handleOpenInLogs}
          className={RESOURCE_TAB_ICON_BUTTON_CLASS}
          aria-label='Open in logs'
        >
          <SquareArrowUpRight className={RESOURCE_TAB_ICON_CLASS} />
        </Button>
      </Tooltip.Trigger>
      <Tooltip.Content side='bottom'>
        <p>Open in logs</p>
      </Tooltip.Content>
    </Tooltip.Root>
  )
}
