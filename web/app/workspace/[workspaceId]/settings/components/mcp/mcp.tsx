'use client'

import { useEffect, useRef, useState } from 'react'
import { useParams } from 'next/navigation'
import { useQueryState } from 'nuqs'
import { McpIcon } from '@/components/icons'
import { canMutateWorkspaceSettingsSection } from '@/components/settings/navigation'
import { Badge, Button, Chip, ChipConfirmModal, cn, Tooltip, toast } from '@/components/ui-kit'
import { ArrowLeft, ChevronDown, Plus } from '@/components/ui-kit/icons'
import { requestJson } from '@/lib/api/client/request'
import { getWorkflowStateContract } from '@/lib/api/contracts/workflows'
import { createLogger } from '@/lib/logger'
import {
  getIssueBadgeLabel,
  getIssueBadgeVariant,
  getMcpToolIssue,
  type McpToolIssue,
} from '@/lib/mcp/tool-validation'
import type { McpTransport } from '@/lib/mcp/types'
import { userFacingError, workspaceCopy } from '@/lib/product-copy'
import type { BlockState } from '@/lib/workflows/domain/workflow'
import { useUserPermissionsContext } from '@/app/workspace/[workspaceId]/providers/workspace-permissions-provider'
import {
  mcpServerIdParam,
  mcpServerIdUrlKeys,
} from '@/app/workspace/[workspaceId]/settings/[section]/search-params'
import { getRefreshActionState } from '@/app/workspace/[workspaceId]/settings/components/mcp/refresh-action-state'
import { getServerToolsLabel } from '@/app/workspace/[workspaceId]/settings/components/mcp/server-tools-label'
import { SettingsEmptyState } from '@/app/workspace/[workspaceId]/settings/components/settings-empty-state'
import { SettingsField } from '@/app/workspace/[workspaceId]/settings/components/settings-field'
import { SettingsPanel } from '@/app/workspace/[workspaceId]/settings/components/settings-panel'
import {
  RESOURCE_LIST_STACK,
  SettingsResourceRow,
} from '@/app/workspace/[workspaceId]/settings/components/settings-resource-row'
import { SettingsSection } from '@/app/workspace/[workspaceId]/settings/components/settings-section/settings-section'
import { useSettingsSearch } from '@/app/workspace/[workspaceId]/settings/components/use-settings-search'
import { useMcpOauthPopup } from '@/hooks/mcp/use-mcp-oauth-popup'
import {
  type McpServer,
  type McpTool,
  useAllowedMcpDomains,
  useCreateMcpServer,
  useDeleteMcpServer,
  useForceRefreshMcpTools,
  useMcpServers,
  useMcpToolsQuery,
  useRefreshMcpServer,
  useStoredMcpTools,
  useUpdateMcpServer,
} from '@/hooks/queries/mcp'
import { useAvailableEnvVarKeys } from '@/hooks/use-available-env-vars'
import { useWorkflowRegistry } from '@/stores/workflows/registry/store'
import { useSubBlockStore } from '@/stores/workflows/subblock/store'
import { McpServerFormModal } from './components'

const logger = createLogger('McpSettings')

function formatTransportLabel(transport: string): string {
  return transport
    .split('-')
    .map((word) =>
      ['http', 'sse', 'stdio'].includes(word.toLowerCase())
        ? word.toUpperCase()
        : word.charAt(0).toUpperCase() + word.slice(1)
    )
    .join('-')
}

interface ServerListItemProps {
  canManage: boolean
  server: McpServer
  tools: McpTool[]
  isConnecting: boolean
  isLoadingTools?: boolean
  isRefreshing?: boolean
  discoveryError?: string | null
  onViewDetails: () => void
  onAuthorize: () => void
}

function ServerListItem({
  canManage,
  server,
  tools,
  isConnecting,
  isLoadingTools = false,
  isRefreshing = false,
  discoveryError = null,
  onViewDetails,
  onAuthorize,
}: ServerListItemProps) {
  const transportLabel = formatTransportLabel(server.transport || 'http')
  const toolsLabel = getServerToolsLabel(
    tools,
    server.connectionStatus,
    server.lastError,
    server.authType
  )
  // Only hard-red when there are no last-known tools to show. A populated, connected server
  // stays on its tool count through a transient probe failure; a persistent failure flips
  // `connectionStatus` to error/disconnected and reads as failed through that path instead.
  const showDiscoveryError =
    Boolean(discoveryError) &&
    tools.length === 0 &&
    server.connectionStatus !== 'error' &&
    server.connectionStatus !== 'disconnected'
  const hasConnectionIssue =
    server.connectionStatus === 'error' ||
    server.connectionStatus === 'disconnected' ||
    showDiscoveryError

  const serverName = server.name || 'Unnamed server'
  // Transport rides on the description rather than beside the name — inside the
  // row's truncating title a long name would clip it away entirely.
  const statusText = isConnecting
    ? 'Waiting for authorization...'
    : isRefreshing
      ? 'Refreshing...'
      : isLoadingTools && tools.length === 0
        ? workspaceCopy.common.states.loading
        : showDiscoveryError
          ? discoveryError
          : toolsLabel

  return (
    <SettingsResourceRow
      icon={<McpIcon className='text-[var(--text-icon)]' />}
      iconFilled
      title={serverName}
      description={
        <>
          {`${transportLabel} · `}
          {/* Only the status reddens — the transport is neutral metadata. */}
          <span
            className={cn(
              hasConnectionIssue && !isConnecting ? 'text-[var(--text-error)]' : undefined
            )}
          >
            {statusText}
          </span>
        </>
      }
      onClick={onViewDetails}
      clickLabel={`Open ${serverName}`}
      navigable
      trailing={
        canManage && server.authType === 'oauth' && server.connectionStatus !== 'connected' ? (
          <Chip onClick={onAuthorize}>{isConnecting ? 'Reopen authorization' : 'Authorize'}</Chip>
        ) : undefined
      }
    />
  )
}

function buildEditInitialData(server: McpServer) {
  const entries: { key: string; value: string }[] = server.headers
    ? Object.entries(server.headers).map(([key, value]) => ({ key, value }))
    : []
  if (entries.length === 0) entries.push({ key: '', value: '' })
  const last = entries[entries.length - 1]
  if (last.key !== '' || last.value !== '') entries.push({ key: '', value: '' })

  return {
    name: server.name || '',
    transport: (server.transport as McpTransport) || 'streamable-http',
    url: server.url || '',
    timeout: 30000,
    headers: entries,
    oauthClientId: server.oauthClientId || undefined,
    hasOauthClientSecret: server.hasOauthClientSecret === true,
  }
}

export function MCP() {
  const params = useParams()
  const workspaceId = params.workspaceId as string
  const workspacePermissions = useUserPermissionsContext()
  const canEdit = canMutateWorkspaceSettingsSection('mcp', workspacePermissions)

  const {
    data: servers = [],
    isLoading: serversLoading,
    error: serversError,
  } = useMcpServers(workspaceId)
  const { data: mcpToolsData = [], toolsStateByServer } = useMcpToolsQuery(workspaceId)
  const { data: storedTools = [], refetch: refetchStoredTools } = useStoredMcpTools(workspaceId)
  const forceRefreshToolsMutation = useForceRefreshMcpTools()
  const forceRefreshTools = forceRefreshToolsMutation.mutate
  const createServerMutation = useCreateMcpServer()
  const deleteServerMutation = useDeleteMcpServer()
  const refreshServerMutation = useRefreshMcpServer()
  const updateServerMutation = useUpdateMcpServer()
  const availableEnvVars = useAvailableEnvVarKeys(workspaceId)
  const { data: allowedMcpDomains = null } = useAllowedMcpDomains()

  const [showAddModal, setShowAddModal] = useState(false)
  const [editingServerId, setEditingServerId] = useState<string | null>(null)

  const [searchTerm, setSearchTerm] = useSettingsSearch()
  const [deletingServers, setDeletingServers] = useState<Set<string>>(() => new Set())
  const { connectingServers: connectingOauthServers, startOauthForServer } = useMcpOauthPopup({
    workspaceId,
  })

  const [serverToDeleteId, setServerToDeleteId] = useState<string | null>(null)
  const showDeleteDialog = serverToDeleteId !== null

  const [selectedServerId, setSelectedServerId] = useQueryState(mcpServerIdParam.key, {
    ...mcpServerIdParam.parser,
    ...mcpServerIdUrlKeys,
  })

  const initialServerIdRef = useRef(selectedServerId)
  const didDeepLinkRefreshRef = useRef(false)
  useEffect(() => {
    if (didDeepLinkRefreshRef.current) return
    if (!initialServerIdRef.current) return
    didDeepLinkRefreshRef.current = true
    if (canEdit) forceRefreshTools(workspaceId)
    refetchStoredTools()
  }, [canEdit, workspaceId, forceRefreshTools, refetchStoredTools])

  const [expandedTools, setExpandedTools] = useState<Set<string>>(() => new Set())

  const handleRemoveServer = (serverId: string) => {
    setServerToDeleteId(serverId)
  }

  const confirmDeleteServer = async () => {
    if (!serverToDeleteId) return

    const serverId = serverToDeleteId
    setServerToDeleteId(null)

    setDeletingServers((prev) => new Set(prev).add(serverId))

    try {
      await deleteServerMutation.mutateAsync({ workspaceId, serverId })
      // Deleting from the detail view leaves a dead id in the URL — drop it so Back
      // doesn't land on a server that no longer exists.
      if (selectedServerId === serverId) handleBackToList()
      logger.info(`Removed MCP server: ${serverId}`)
    } catch (error) {
      logger.error('Failed to remove MCP server:', error)
      toast.error('删除 MCP 服务器失败', {
        description: userFacingError(error, 'deleteFailed'),
      })
    } finally {
      setDeletingServers((prev) => {
        const newSet = new Set(prev)
        newSet.delete(serverId)
        return newSet
      })
    }
  }

  const toolsByServer = (mcpToolsData || []).reduce(
    (acc, tool) => {
      if (!tool?.serverId) return acc
      if (!acc[tool.serverId]) {
        acc[tool.serverId] = []
      }
      acc[tool.serverId].push(tool)
      return acc
    },
    {} as Record<string, typeof mcpToolsData>
  )

  const filteredServers = (servers || []).filter((server) =>
    server.name?.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const handleViewDetails = (serverId: string) => {
    setSelectedServerId(serverId)
    if (canEdit) forceRefreshTools(workspaceId)
    refetchStoredTools()
  }

  /** Closing replaces the URL — Back should leave the section, not reopen the detail view. */
  const handleBackToList = () => {
    setSelectedServerId(null, { history: 'replace' })
    setExpandedTools(new Set())
  }

  const toggleToolExpanded = (toolName: string) => {
    setExpandedTools((prev) => {
      const newSet = new Set(prev)
      if (newSet.has(toolName)) {
        newSet.delete(toolName)
      } else {
        newSet.add(toolName)
      }
      return newSet
    })
  }

  const handleRefreshServer = async (serverId: string) => {
    try {
      const result = await refreshServerMutation.mutateAsync({ workspaceId, serverId })
      logger.info(
        `Refreshed MCP server: ${serverId}, workflows updated: ${result.workflowsUpdated}`
      )

      const activeWorkflowId = useWorkflowRegistry.getState().activeWorkflowId
      if (activeWorkflowId && result.updatedWorkflowIds?.includes(activeWorkflowId)) {
        logger.info(`Active workflow ${activeWorkflowId} was updated, reloading subblock values`)
        try {
          const { data: workflowData } = await requestJson(getWorkflowStateContract, {
            params: { id: activeWorkflowId },
          })
          if (workflowData?.state?.blocks) {
            useSubBlockStore
              .getState()
              .initializeFromWorkflow(
                activeWorkflowId,
                workflowData.state.blocks as Record<string, BlockState>
              )
          }
        } catch (reloadError) {
          logger.warn('Failed to reload workflow subblock values:', reloadError)
        }
      }
    } catch (error) {
      logger.error('Failed to refresh MCP server:', error)
      toast.error('刷新 MCP 服务器失败', {
        description: userFacingError(error, 'loadFailed'),
      })
    }
  }

  useEffect(() => {
    if (!refreshServerMutation.isSuccess && !refreshServerMutation.isError) return
    const timeout = window.setTimeout(() => refreshServerMutation.reset(), 3000)
    return () => window.clearTimeout(timeout)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mutation object is unstable; status flags are the triggers
  }, [refreshServerMutation.isSuccess, refreshServerMutation.isError])

  const editingServer = editingServerId
    ? (servers.find((s) => s.id === editingServerId) as McpServer | undefined)
    : undefined
  const editInitialData = editingServer ? buildEditInitialData(editingServer) : undefined

  const selectedServer = (() => {
    if (!selectedServerId) return null
    const server = servers.find((s) => s.id === selectedServerId) as McpServer | undefined
    if (!server) return null
    const serverTools = (toolsByServer[selectedServerId] || []) as McpTool[]
    return { server, tools: serverTools }
  })()

  const getStoredToolIssues = (
    serverId: string,
    toolName: string
  ): { issue: McpToolIssue; workflowName: string }[] => {
    const relevantStoredTools = storedTools.filter(
      (st) => st.serverId === serverId && st.toolName === toolName
    )

    const serverStates = servers.map((s) => ({
      id: s.id,
      url: s.url,
      connectionStatus: s.connectionStatus,
      lastError: s.lastError || undefined,
    }))

    const discoveredTools = mcpToolsData.map((t) => ({
      serverId: t.serverId,
      name: t.name,
      inputSchema: t.inputSchema,
    }))

    const issues: { issue: McpToolIssue; workflowName: string }[] = []

    for (const storedTool of relevantStoredTools) {
      const issue = getMcpToolIssue(
        {
          serverId: storedTool.serverId,
          serverUrl: storedTool.serverUrl,
          toolName: storedTool.toolName,
          schema: storedTool.schema,
        },
        serverStates,
        discoveredTools
      )

      if (issue) {
        issues.push({ issue, workflowName: storedTool.workflowName })
      }
    }

    return issues
  }

  // Only a failure to load the server LIST replaces the list. A tool-discovery failure must
  // not blank the page — the servers still render, each row surfacing its own discovery
  // state via `toolsStateByServer`.
  const listError = serversError
  const hasServers = servers && servers.length > 0
  const showNoResults = searchTerm.trim() && filteredServers.length === 0 && servers.length > 0

  // Delete is reachable from both the list and the detail header, so the confirm
  // modal has to render in whichever branch is mounted.
  const deleteConfirmModal = canEdit ? (
    <ChipConfirmModal
      open={showDeleteDialog}
      onOpenChange={(open) => {
        if (!open) setServerToDeleteId(null)
      }}
      srTitle='删除 MCP 服务器'
      title='删除 MCP 服务器'
      text={[
        'Are you sure you want to delete ',
        {
          text: servers.find((s) => s.id === serverToDeleteId)?.name || '此服务器',
          bold: true,
        },
        '? This action cannot be undone.',
      ]}
      confirm={{ label: '删除', onClick: confirmDeleteServer }}
    />
  ) : null

  if (selectedServer) {
    const { server, tools } = selectedServer
    const transportLabel = formatTransportLabel(server.transport || 'http')
    const isCurrentRefresh = refreshServerMutation.variables?.serverId === server.id
    const refreshAction = getRefreshActionState({
      mutationStatus: isCurrentRefresh ? refreshServerMutation.status : 'idle',
      connectionStatus: isCurrentRefresh ? refreshServerMutation.data?.status : undefined,
      workflowsUpdated: isCurrentRefresh ? refreshServerMutation.data?.workflowsUpdated : undefined,
    })

    return (
      <SettingsPanel
        back={{ text: 'MCP tools', icon: ArrowLeft, onSelect: handleBackToList }}
        title={server.name || 'Unnamed server'}
        actions={
          canEdit
            ? [
                {
                  text: refreshAction.text,
                  textTone: refreshAction.textTone,
                  onSelect: () => handleRefreshServer(server.id),
                  disabled: refreshAction.disabled,
                },
                {
                  text: 'Edit',
                  onSelect: () => setEditingServerId(server.id),
                },
                {
                  id: 'delete',
                  text: deletingServers.has(server.id) ? '正在删除…' : '删除',
                  onSelect: () => handleRemoveServer(server.id),
                  disabled: deletingServers.has(server.id),
                },
              ]
            : []
        }
      >
        <SettingsSection label='Server'>
          <div className='flex flex-col gap-4.5'>
            <SettingsField label='Server name'>{server.name || 'Unnamed server'}</SettingsField>

            <SettingsField label='Transport'>{transportLabel}</SettingsField>

            {server.url && (
              <SettingsField label='URL' breakAll>
                {server.url}
              </SettingsField>
            )}

            {server.connectionStatus !== 'connected' && (
              <SettingsField label='Status'>
                <p className='text-[var(--text-error)] text-sm'>
                  {getServerToolsLabel(
                    [],
                    server.connectionStatus,
                    server.lastError,
                    server.authType
                  )}
                </p>
              </SettingsField>
            )}

            {canEdit && server.authType === 'oauth' && server.connectionStatus !== 'connected' && (
              <SettingsField label='Authentication'>
                <div>
                  <Chip
                    variant='primary'
                    onClick={async () => {
                      await startOauthForServer(server.id)
                    }}
                  >
                    {connectingOauthServers.has(server.id) ? 'Reopen authorization' : 'Authorize'}
                  </Chip>
                </div>
              </SettingsField>
            )}
          </div>
        </SettingsSection>

        <SettingsSection label={`Tools (${tools.length})`}>
          {tools.length === 0 ? (
            <p className='text-[var(--text-muted)] text-sm'>暂无可用工具</p>
          ) : (
            <div className='flex flex-col gap-2'>
              {tools.map((tool) => {
                const issues = getStoredToolIssues(server.id, tool.name)
                const affectedWorkflows = issues.map((i) => i.workflowName)
                const isExpanded = expandedTools.has(tool.name)
                const hasParams =
                  tool.inputSchema?.properties &&
                  Object.keys(tool.inputSchema.properties).length > 0
                const requiredParams = tool.inputSchema?.required || []

                return (
                  <div
                    key={tool.name}
                    className='overflow-hidden rounded-md border border-[var(--border-1)] bg-[var(--surface-3)]'
                  >
                    <Button
                      type='button'
                      variant='ghost'
                      onClick={() => hasParams && toggleToolExpanded(tool.name)}
                      className={cn(
                        'flex h-auto w-full items-start justify-between rounded-none px-2.5 py-2 text-left text-sm',
                        hasParams && 'cursor-pointer hover-hover:bg-[var(--surface-4)]'
                      )}
                      disabled={!hasParams}
                    >
                      <div className='flex-1'>
                        <div className='flex h-[16px] items-center gap-1.5'>
                          <p className='text-[var(--text-primary)] text-sm leading-none'>
                            {tool.name}
                          </p>
                          {issues.length > 0 && (
                            <Tooltip.Root>
                              <Tooltip.Trigger asChild>
                                <div className='flex items-center'>
                                  <Badge variant={getIssueBadgeVariant(issues[0].issue)} size='sm'>
                                    {getIssueBadgeLabel(issues[0].issue)}
                                  </Badge>
                                </div>
                              </Tooltip.Trigger>
                              <Tooltip.Content>
                                Update in: {affectedWorkflows.join(', ')}
                              </Tooltip.Content>
                            </Tooltip.Root>
                          )}
                        </div>
                        {tool.description && (
                          <p className='mt-1 text-[var(--text-tertiary)] text-sm'>
                            {tool.description}
                          </p>
                        )}
                      </div>
                      {hasParams && (
                        <ChevronDown
                          className={cn(
                            'mt-0.5 size-[14px] flex-shrink-0 text-[var(--text-muted)] transition-transform duration-200',
                            isExpanded && 'rotate-180'
                          )}
                        />
                      )}
                    </Button>

                    {isExpanded && hasParams && (
                      <div className='border-[var(--border-1)] border-t bg-[var(--surface-2)] px-2.5 py-2'>
                        <p className='mb-1.5 text-[var(--text-muted)] text-caption uppercase tracking-wide'>
                          Parameters
                        </p>
                        <div className='flex flex-col gap-1.5'>
                          {Object.entries(tool.inputSchema!.properties!).map(
                            ([paramName, param]) => {
                              const isRequired = requiredParams.includes(paramName)
                              const paramType =
                                typeof param === 'object' && param !== null
                                  ? (param as { type?: string }).type || 'any'
                                  : 'any'
                              const paramDesc =
                                typeof param === 'object' && param !== null
                                  ? (param as { description?: string }).description
                                  : undefined

                              return (
                                <div
                                  key={paramName}
                                  className='rounded-sm border border-[var(--border-1)] bg-[var(--surface-3)] px-2 py-1.5'
                                >
                                  <div className='flex items-center gap-1.5'>
                                    <span className='text-[var(--text-primary)] text-small'>
                                      {paramName}
                                    </span>
                                    <Badge variant='outline' size='sm'>
                                      {paramType}
                                    </Badge>
                                    {isRequired && (
                                      <Badge variant='default' size='sm'>
                                        required
                                      </Badge>
                                    )}
                                  </div>
                                  {paramDesc && (
                                    <p className='mt-[3px] text-[var(--text-tertiary)] text-caption leading-relaxed'>
                                      {paramDesc}
                                    </p>
                                  )}
                                </div>
                              )
                            }
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </SettingsSection>

        {canEdit && (
          <McpServerFormModal
            open={editingServerId !== null}
            onOpenChange={(open) => {
              if (!open) setEditingServerId(null)
            }}
            mode='edit'
            initialData={editInitialData}
            onSubmit={async (config) => {
              const currentServer = servers.find((s) => s.id === selectedServerId)
              await updateServerMutation.mutateAsync({
                workspaceId,
                serverId: selectedServerId!,
                updates: {
                  ...config,
                  enabled: currentServer?.enabled ?? true,
                },
              })
            }}
            workspaceId={workspaceId}
            availableEnvVars={availableEnvVars}
            allowedMcpDomains={allowedMcpDomains}
          />
        )}
        {deleteConfirmModal}
      </SettingsPanel>
    )
  }

  return (
    <>
      <SettingsPanel
        search={{
          value: searchTerm,
          onChange: setSearchTerm,
          placeholder: '搜索服务器…',
        }}
        actions={
          canEdit
            ? [
                {
                  text: '添加服务器',
                  icon: Plus,
                  variant: 'primary',
                  onSelect: () => setShowAddModal(true),
                  disabled: serversLoading,
                },
              ]
            : []
        }
      >
        {listError ? (
          <SettingsEmptyState tone='error'>
            {userFacingError(listError, 'loadFailed')}
          </SettingsEmptyState>
        ) : serversLoading ? (
          <SettingsEmptyState>{workspaceCopy.common.states.loading}</SettingsEmptyState>
        ) : !hasServers ? (
          <SettingsEmptyState>
            {canEdit ? '点击上方“添加服务器”开始配置' : '尚未配置 MCP 服务器'}
          </SettingsEmptyState>
        ) : (
          <div className={RESOURCE_LIST_STACK}>
            {filteredServers.map((server) => {
              if (!server?.id) return null
              const tools = toolsByServer[server.id] || []
              const serverToolsState = toolsStateByServer.get(server.id)
              const isLoadingTools = serverToolsState
                ? serverToolsState.isLoading || serverToolsState.isFetching
                : false

              return (
                <ServerListItem
                  key={server.id}
                  canManage={canEdit}
                  server={server}
                  tools={tools}
                  isConnecting={connectingOauthServers.has(server.id)}
                  isLoadingTools={isLoadingTools}
                  isRefreshing={
                    refreshServerMutation.isPending &&
                    refreshServerMutation.variables?.serverId === server.id
                  }
                  discoveryError={
                    serverToolsState?.error
                      ? userFacingError(serverToolsState.error, 'loadFailed')
                      : null
                  }
                  onViewDetails={() => handleViewDetails(server.id)}
                  onAuthorize={() => startOauthForServer(server.id)}
                />
              )
            })}
            {showNoResults && (
              <SettingsEmptyState variant='inline'>
                没有找到与“{searchTerm}”匹配的服务器
              </SettingsEmptyState>
            )}
          </div>
        )}
      </SettingsPanel>

      {canEdit && (
        <McpServerFormModal
          open={showAddModal}
          onOpenChange={setShowAddModal}
          mode='add'
          onSubmit={async (config) => {
            const result = await createServerMutation.mutateAsync({
              workspaceId,
              config: { ...config, enabled: true },
            })
            if (result.authType === 'oauth') {
              await startOauthForServer(result.serverId)
            }
          }}
          workspaceId={workspaceId}
          availableEnvVars={availableEnvVars}
          allowedMcpDomains={allowedMcpDomains}
        />
      )}

      {deleteConfirmModal}
    </>
  )
}
