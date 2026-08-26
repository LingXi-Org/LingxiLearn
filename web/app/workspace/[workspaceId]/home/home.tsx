'use client'

import { type PointerEvent, useCallback, useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useParams } from 'next/navigation'
import { usePostHog } from 'posthog-js/react'
import { cn, toast } from '@/components/ui-kit'
import { LandingPromptStorage, MothershipHandoffStorage } from '@/lib/core/utils/browser-storage'
import type { ChatContext } from '@/lib/lingxi/chat-context'
import { LINGXI_EXCLUDED_RESOURCE_TYPES } from '@/lib/lingxi/supported-contexts'
import { createLogger } from '@/lib/logger'
import {
  addMothershipContexts,
  MOTHERSHIP_SEND_MESSAGE_EVENT,
  type MothershipSendMessageDetail,
} from '@/lib/mothership/events'
import { captureEvent } from '@/lib/posthog/client'
import { RESOURCE_HEADER_CLASSES } from '@/app/workspace/[workspaceId]/home/components/mothership-view/components/resource-tabs/resource-tab-controls'
import { resolveWorkspaceResourceRef } from '@/app/workspace/[workspaceId]/home/resolve-resource-ref'
import {
  useMarkMothershipChatRead,
  useMothershipChatHistory,
} from '@/hooks/queries/mothership-chats'
import { getWorkspaceFilesQueryOptions, useWorkspaceFiles } from '@/hooks/queries/workspace-files'
import { useOAuthReturnRouter } from '@/hooks/use-oauth-return'
import { ChatFeature } from './chat-feature'
import { WorkspaceResourcePanel } from './components/workspace-resource-panel'
import {
  isResourceReferencedByContexts,
  resourceFromContext,
  resourceTitleFromContext,
} from './context-resource-projection'
import {
  createLingxiTaskTransport,
  getLingxiGraphUseChatOptions,
  useMothershipResize,
  useWorkspaceChatController,
} from './hooks'
import { toResourceActivityNotice } from './hooks/lingxi-resource-activity-adapter'
import {
  useWorkspacePanelController,
  useWorkspacePanelSynchronization,
} from './hooks/use-workspace-panel-controller'
import type { FileAttachmentForApi, MothershipResource, WorkspaceResourceRef } from './types'

const logger = createLogger('Home')

const LINGXI_GREETINGS = [
  '今天想学点什么？',
  '准备从哪里开始？',
  '今天一起攻克什么？',
  '来规划今天的学习吧。',
  '有什么知识想深入了解？',
] as const

const GREETING_STORAGE_PREFIX = 'lingxi-home-greeting:'

interface WorkspaceHomeShellProps {
  chatId?: string
  userId?: string
  /** Resolved server-side by the page — the embedded table can't reach AppConfig. */
  tableViewsEnabled?: boolean
}

export function WorkspaceHomeShell({ chatId, userId, tableViewsEnabled }: WorkspaceHomeShellProps) {
  useOAuthReturnRouter()
  const { workspaceId } = useParams<{ workspaceId: string }>()
  const queryClient = useQueryClient()
  const panel = useWorkspacePanelController()
  const [greeting, setGreeting] = useState<(typeof LINGXI_GREETINGS)[number]>(LINGXI_GREETINGS[0])
  const { data: workspaceFiles = [] } = useWorkspaceFiles(workspaceId)
  const posthog = usePostHog()
  const posthogRef = useRef(posthog)
  posthogRef.current = posthog
  const [initialPrompt, setInitialPrompt] = useState('')
  const hasCheckedLandingStorageRef = useRef(false)
  const initialViewInputRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const storageKey = `${GREETING_STORAGE_PREFIX}${userId ?? 'anonymous'}`

    try {
      const storedIndex = Number.parseInt(sessionStorage.getItem(storageKey) ?? '', 10)
      if (storedIndex >= 0 && storedIndex < LINGXI_GREETINGS.length) {
        setGreeting(LINGXI_GREETINGS[storedIndex])
        return
      }

      const nextIndex = Math.floor(Math.random() * LINGXI_GREETINGS.length)
      sessionStorage.setItem(storageKey, String(nextIndex))
      setGreeting(LINGXI_GREETINGS[nextIndex])
    } catch {
      // Storage can be unavailable in privacy-restricted browser contexts.
      setGreeting(LINGXI_GREETINGS[Math.floor(Math.random() * LINGXI_GREETINGS.length)])
    }
  }, [userId])

  const [isInputEntering, setIsInputEntering] = useState(false)

  useEffect(() => {
    if (hasCheckedLandingStorageRef.current) return
    hasCheckedLandingStorageRef.current = true

    const prompt = LandingPromptStorage.consume()
    if (prompt) {
      logger.info('Retrieved landing page prompt, populating home input')
      setInitialPrompt(prompt)
    }
  }, [])

  const wasSendingRef = useRef(false)

  // Lingxi mode closes the context-chip vocabulary to what its backend can
  // actually consume (issue #18 §13); Sim keeps the full catalog.
  const excludedResourceTypes =
    workspaceId === 'lingxi' ? LINGXI_EXCLUDED_RESOURCE_TYPES : undefined

  const { isPending: isChatHistoryPending } = useMothershipChatHistory(
    workspaceId === 'lingxi' ? undefined : chatId
  )
  const { mutate: markRead } = useMarkMothershipChatRead(workspaceId)

  const chatOptions = getLingxiGraphUseChatOptions({
    adapter: createLingxiTaskTransport(),
    onResourceEvent: (resourceId, eventKind) =>
      panel.notice(toResourceActivityNotice(resourceId, eventKind)),
    activeResourceState: panel.activeResourceState,
    onRequestStarted: ({ requestId, userMessageId }) => {
      captureEvent(posthogRef.current, 'task_request_started', {
        workspace_id: workspaceId,
        view: 'mothership',
        request_id: requestId,
        user_message_id: userMessageId,
      })
    },
  })

  const {
    messages,
    isSending,
    isReconnecting,
    resolvedChatId,
    desktopScopeId,
    sendMessage,
    answerInteraction,
    stopGeneration,
    resources,
    activeResourceId,
    setActiveResourceId,
    addResource,
    removeResource,
    reorderResources,
    messageQueue,
    removeFromQueue,
    sendNow,
    editQueuedMessage,
    cancelQueueEdit,
    editingQueuedId,
    dispatchingHeadId,
    previewSession,
    genericResourceData,
    lingxiRuntime,
    getCurrentRequestId,
  } = useWorkspaceChatController(workspaceId, chatId, chatOptions)

  const { mothershipRef, handleResizePointerDown, clearWidth } = useMothershipResize(desktopScopeId)
  const resourceAttentionChatIdRef = useRef(resolvedChatId)

  const collapseResource = useCallback(
    () => panel.collapse(clearWidth),
    [panel.collapse, clearWidth]
  )

  const selectResourceFromUser = useCallback(
    (resourceId: string) => {
      panel.select(resourceId, setActiveResourceId)
    },
    [panel.select, setActiveResourceId]
  )

  const addResourceFromUser = useCallback(
    (resource: MothershipResource) => {
      panel.add(resource, addResource, setActiveResourceId)
    },
    [panel.add, addResource, setActiveResourceId]
  )

  const handleResourceResizePointerDown = useCallback(
    (event: PointerEvent<HTMLDivElement>) => {
      panel.resize(event, handleResizePointerDown)
    },
    [panel.resize, handleResizePointerDown]
  )

  const handleResourceInteraction = panel.markInteraction

  useEffect(() => {
    const previousChatId = resourceAttentionChatIdRef.current
    resourceAttentionChatIdRef.current = resolvedChatId
    wasSendingRef.current = false
    if (resolvedChatId) {
      markRead(resolvedChatId)
    } else {
      panel.resetForThread(clearWidth)
    }
    if (!resolvedChatId || (previousChatId && previousChatId !== resolvedChatId)) {
      panel.resetForThread(clearWidth)
    }
  }, [resolvedChatId, markRead, clearWidth, workspaceId, panel.resetForThread])

  useEffect(() => {
    if (wasSendingRef.current && !isSending && resolvedChatId) {
      markRead(resolvedChatId)
    }
    wasSendingRef.current = isSending
  }, [isSending, resolvedChatId, markRead, workspaceId])

  useWorkspacePanelSynchronization(panel, resources, clearWidth)

  const handleStopGeneration = useCallback(() => {
    captureEvent(posthogRef.current, 'task_generation_aborted', {
      workspace_id: workspaceId,
      view: 'mothership',
      request_id: getCurrentRequestId(),
    })
    void stopGeneration().catch(() => {})
  }, [workspaceId, getCurrentRequestId, stopGeneration])

  const handleSubmit = useCallback(
    (text: string, fileAttachments?: FileAttachmentForApi[], contexts?: ChatContext[]) => {
      const trimmed = text.trim()
      if (!trimmed && !(fileAttachments && fileAttachments.length > 0)) return

      captureEvent(posthogRef.current, 'task_message_sent', {
        workspace_id: workspaceId,
        has_attachments: !!(fileAttachments && fileAttachments.length > 0),
        has_contexts: !!(contexts && contexts.length > 0),
        is_new_task: !chatId,
      })

      if (initialViewInputRef.current) {
        setIsInputEntering(true)
      }

      panel.prepareForRequest()
      sendMessage(trimmed || 'Analyze the attached file(s).', fileAttachments, contexts)
    },
    [workspaceId, chatId, sendMessage, panel.prepareForRequest]
  )

  /**
   * Handles cross-surface send requests (terminal/console "Fix in Chat", the
   * log "Troubleshoot in Chat" action). `preventDefault` claims the event so a
   * producer that dispatched it while this chat is mounted knows a live chat
   * consumed the message and skips its navigate-and-persist fallback.
   */
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<MothershipSendMessageDetail>).detail
      if (!detail?.message) return
      e.preventDefault()
      sendMessage(detail.message, detail.fileAttachments, detail.contexts, {
        ...(detail.resumeUserMessageId ? { resumeUserMessageId: detail.resumeUserMessageId } : {}),
      })
    }
    window.addEventListener(MOTHERSHIP_SEND_MESSAGE_EVENT, handler)
    return () => window.removeEventListener(MOTHERSHIP_SEND_MESSAGE_EVENT, handler)
  }, [sendMessage])

  /**
   * Consumes a one-shot handoff left by another surface and applies it to this
   * fresh chat. Two shapes arrive here: a message handoff (e.g. "Troubleshoot in
   * Chat" on an errored log) is auto-sent with its contexts attached; a
   * chip-only handoff (highlight-to-chat from the standalone Files/Tables pages)
   * seeds reference chips and sends nothing.
   *
   * Only the cross-route path lands here — when a chat is already mounted the
   * events deliver directly. Gated to the new-chat surface (`!chatId`): a
   * handoff always targets a fresh chat, so an existing `/chat/[chatId]` mount
   * must never claim it if navigation races. `consume` clears the entry
   * atomically, so it fires at most once even across a StrictMode remount.
   *
   * Chip-only handoffs open each resource directly rather than relying on the
   * input's listener being mounted, then dispatch so the input inserts the chip.
   * This effect is declared after `useWorkspaceChatController`, so its chat-init `setResources([])`
   * has already flushed and cannot wipe the just-opened resource.
   */
  useEffect(() => {
    if (chatId) return
    const handoff = MothershipHandoffStorage.consume(workspaceId)
    if (!handoff) return
    if (handoff.message) {
      sendMessage(handoff.message, handoff.fileAttachments, handoff.contexts, {
        ...(handoff.resumeUserMessageId
          ? { resumeUserMessageId: handoff.resumeUserMessageId }
          : {}),
      })
      return
    }
    const contexts = handoff.contexts ?? []
    for (const context of contexts) handleContextAdd(context)
    addMothershipContexts(contexts)
    // `handleContextAdd` is a body function, so it is a new value every render;
    // listing it would re-run this drain on every render. Omitted deliberately to
    // keep it one-shot — and harmless either way, since `consume` clears the entry
    // atomically and any re-run would find nothing.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- see above
  }, [chatId, workspaceId, sendMessage])

  function handleContextAdd(context: ChatContext) {
    const resolved = resourceFromContext(context)
    if (resolved) {
      addResourceFromUser({
        ...resolved,
        title: resourceTitleFromContext(context),
      })
    }
  }

  function handleInitialContextRemove(context: ChatContext, remaining: ChatContext[]) {
    const resolved = resourceFromContext(context)
    if (!resolved) return
    // A whole-file chip and one or more of its selection chips (or several
    // selections of the same file/table) all resolve to the same resource tab.
    // Only close the tab once no remaining chip still references it, so removing
    // one of several chips doesn't yank a slideover the others still point at.
    if (isResourceReferencedByContexts(resolved, remaining)) return
    removeResource(resolved.type, resolved.id)
  }

  function openWorkspaceResource(resource: MothershipResource) {
    addResourceFromUser(resource)
  }

  /**
   * Opens the resource a message chip points at, resolving it first. A chip may
   * carry only a filename — the agent names a file before the client's file
   * list knows it exists — so one forced refetch closes that window. What still
   * resolves to nothing opens nothing, rather than a tab that cannot be
   * viewed or removed.
   */
  async function handleWorkspaceResourceSelect(ref: WorkspaceResourceRef) {
    const immediate = resolveWorkspaceResourceRef(ref, workspaceFiles)
    if (immediate) {
      openWorkspaceResource(immediate)
      return
    }
    if (ref.type !== 'file') return

    // `staleTime: 0` forces the fetch this branch exists for — the cached list
    // is what already failed to resolve. `fetchQuery` rejects on error and this
    // handler is invoked as a void callback, so failure becomes null rather
    // than an unhandled rejection — and stays distinct from an empty list, so
    // "we could not look" is never reported as "it is not there".
    const files = await queryClient
      .fetchQuery({
        ...getWorkspaceFilesQueryOptions(workspaceId),
        staleTime: 0,
      })
      .catch(() => null)
    const resolved = files && resolveWorkspaceResourceRef(ref, files)
    if (resolved) {
      openWorkspaceResource(resolved)
      return
    }
    // The chip looks clickable, so refusing silently reads as a broken button.
    toast.error(
      files ? `在此工作区中找不到“${ref.title}”` : `无法打开“${ref.title}”，请检查网络后重试`
    )
    logger.warn('Ignored a resource chip that did not resolve', {
      type: ref.type,
      title: ref.title,
      hasPath: Boolean(ref.path),
      reachedWorkspace: files !== null,
    })
  }

  const hasMessages = messages.length > 0
  const showChatSkeleton = Boolean(chatId) && !hasMessages && isChatHistoryPending
  const draftScopeKey = `${workspaceId}:${chatId ?? 'new'}`

  // The empty state is the chat pane's content, not a layout of its own. It
  // used to return early, which meant the resource panel and its toggle did
  // not exist until the first message — so there was no way to open a resource
  // while composing the very prompt that needed one.
  const showEmptyState = !hasMessages && !showChatSkeleton

  return (
    <div
      className={cn('relative flex h-full min-w-0 bg-[var(--bg)]', RESOURCE_HEADER_CLASSES.layout)}
    >
      <ChatFeature
        showEmptyState={showEmptyState}
        greeting={greeting}
        inputContainerRef={initialViewInputRef}
        surfaceProps={{
          userId,
          onContextAdd: handleContextAdd,
          onContextRemove: handleInitialContextRemove,
        }}
        inputProps={{
          defaultValue: initialPrompt,
          draftScopeKey,
          onSubmit: handleSubmit,
          isSending,
          onStopGeneration: handleStopGeneration,
          excludedResourceTypes,
        }}
        transcriptProps={{
          messages,
          isSending,
          isReconnecting,
          isLoading: showChatSkeleton,
          onSubmit: handleSubmit,
          onStopGeneration: handleStopGeneration,
          onQuestionSubmit: answerInteraction,
          messageQueue,
          editingQueuedId,
          dispatchingHeadId,
          onRemoveQueuedMessage: removeFromQueue,
          onSendQueuedMessage: sendNow,
          onEditQueuedMessage: editQueuedMessage,
          onCancelQueueEdit: cancelQueueEdit,
          userId,
          chatId: resolvedChatId,
          onContextAdd: handleContextAdd,
          onWorkspaceResourceSelect: handleWorkspaceResourceSelect,
          draftScopeKey,
          animateInput: isInputEntering,
          onInputAnimationEnd: isInputEntering ? () => setIsInputEntering(false) : undefined,
          initialScrollBlocked: resources.length > 0 && panel.isCollapsed,
          excludedResourceTypes,
        }}
      />

      <WorkspaceResourcePanel
        panelRef={mothershipRef}
        workspaceId={workspaceId}
        chatId={resolvedChatId}
        desktopScopeId={desktopScopeId}
        resources={resources}
        activeResourceId={activeResourceId}
        activityResourceIds={panel.activityIds}
        isCollapsed={panel.isCollapsed}
        previewSession={previewSession}
        isAgentResponding={isSending}
        genericResourceData={genericResourceData ?? undefined}
        lingxiRuntime={lingxiRuntime}
        tableViewsEnabled={tableViewsEnabled}
        onUserInteraction={handleResourceInteraction}
        skipTransition={panel.skipTransition}
        onResizePointerDown={handleResourceResizePointerDown}
        onExpand={panel.expand}
        onCollapse={collapseResource}
        onSelect={selectResourceFromUser}
        onAdd={addResourceFromUser}
        onRemove={removeResource}
        onReorder={reorderResources}
      />
    </div>
  )
}
