import {
  type Dispatch,
  type MutableRefObject,
  type PointerEvent,
  type SetStateAction,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { useQueryState } from 'nuqs'
import { resourceParam, resourceUrlKeys } from '../search-params'
import type { MothershipResource } from '../types'

export type ResourceActivityNotice = {
  resourceId: string
  activation: 'clear' | 'reveal' | 'activity'
}

/**
 * The state owned by the resource-panel view, kept separate from the URL
 * selection.  Keeping this shape serialisation-free makes the transition
 * rules testable without mounting a component or providing a nuqs adapter.
 */
export interface WorkspacePanelViewState {
  isCollapsed: boolean
  activityIds: Set<string>
  userOwnsView: boolean
}

export interface WorkspacePanelResourceState {
  isCollapsed: boolean
  activeResourceId: string | null
  activityIds: ReadonlySet<string>
}

export interface ResourceActivityNoticeDecision extends WorkspacePanelResourceState {
  /** Whether the caller should update the URL/resource selection. */
  shouldSelect: boolean
}

export interface WorkspacePanelSelectionDecision {
  activeResourceId: string
  activityIds: Set<string>
  userOwnsView: true
  /** False when the requested resource is already selected. */
  shouldSelect: boolean
}

export interface WorkspacePanelReconciliationDecision extends WorkspacePanelViewState {
  /** The caller should drop the imperative width when this is true. */
  shouldClearWidth: boolean
  /** The expansion was automatic and may skip the CSS transition once. */
  shouldSkipTransition: boolean
}

function copyActivityIds(activityIds: ReadonlySet<string>): Set<string> {
  return new Set(activityIds)
}

/**
 * Decide how a stream event changes the panel without performing React or URL
 * side effects. Activity never steals an existing user selection: it selects
 * the first resource, highlights a background resource, or consumes the
 * marker for the resource that is already active.
 */
export function applyResourceActivityNotice(
  state: WorkspacePanelResourceState,
  notice: ResourceActivityNotice
): ResourceActivityNoticeDecision {
  const activityIds = copyActivityIds(state.activityIds)

  if (notice.activation === 'clear') {
    activityIds.delete(notice.resourceId)
    return { ...state, activityIds, shouldSelect: false }
  }

  const active = state.activeResourceId
  const isActive = active === notice.resourceId
  const shouldSelect = active === null

  if (active !== null && !isActive) {
    activityIds.add(notice.resourceId)
  } else if (isActive) {
    activityIds.delete(notice.resourceId)
  }

  return {
    isCollapsed: false,
    activeResourceId: shouldSelect ? notice.resourceId : active,
    activityIds,
    shouldSelect,
  }
}

/** Apply a user resource selection and mark the panel as user-owned. */
export function selectWorkspaceResource(
  state: Pick<WorkspacePanelResourceState, 'activeResourceId' | 'activityIds'>,
  resourceId: string
): WorkspacePanelSelectionDecision {
  const activityIds = copyActivityIds(state.activityIds)
  activityIds.delete(resourceId)
  return {
    activeResourceId: resourceId,
    activityIds,
    userOwnsView: true,
    shouldSelect: state.activeResourceId !== resourceId,
  }
}

/** Mark a view interaction as an explicit user decision. */
export function markWorkspacePanelUserOwnership(
  state: WorkspacePanelViewState
): WorkspacePanelViewState {
  return { ...state, userOwnsView: true, activityIds: copyActivityIds(state.activityIds) }
}

/** Clear transient activity before a new request while preserving the view. */
export function prepareWorkspacePanelState(
  state: WorkspacePanelViewState
): WorkspacePanelViewState {
  return { ...state, activityIds: new Set(), userOwnsView: false }
}

/** Reset the panel boundary for a different thread. */
export function resetWorkspacePanelState(): WorkspacePanelViewState {
  return { isCollapsed: true, activityIds: new Set(), userOwnsView: false }
}

/**
 * Reconcile projected resources with panel chrome.  Automatic expansion is
 * suppressed after a user explicitly collapsed or resized the panel, while
 * stale activity markers are always removed.
 */
export function reconcileWorkspacePanelState(
  state: WorkspacePanelViewState,
  resources: ReadonlyArray<Pick<MothershipResource, 'id'>>
): WorkspacePanelReconciliationDecision {
  const shouldExpand = resources.length > 0 && state.isCollapsed && !state.userOwnsView
  const shouldCollapse = resources.length === 0 && !state.isCollapsed
  const resourceIds = new Set(resources.map((resource) => resource.id))
  const activityIds = new Set([...state.activityIds].filter((id) => resourceIds.has(id)))

  return {
    isCollapsed: shouldExpand ? false : shouldCollapse ? true : state.isCollapsed,
    activityIds,
    userOwnsView: state.userOwnsView,
    shouldClearWidth: shouldCollapse,
    shouldSkipTransition: shouldExpand,
  }
}

export interface WorkspacePanelController {
  activeResourceState: [string | null, Dispatch<SetStateAction<string | null>>]
  activeResourceIdRef: MutableRefObject<string | null>
  activityIds: Set<string>
  isCollapsed: boolean
  skipTransition: boolean
  userOwnsViewRef: MutableRefObject<boolean>
  notice: (notice: ResourceActivityNotice) => void
  collapse: (clearWidth: () => void) => void
  expand: () => void
  select: (resourceId: string, selectResource: (resourceId: string) => void) => void
  add: (
    resource: MothershipResource,
    addResource: (resource: MothershipResource) => boolean,
    selectResource: (resourceId: string) => void
  ) => void
  resize: (
    event: PointerEvent<HTMLDivElement>,
    startResize: (event: PointerEvent<HTMLDivElement>) => void
  ) => void
  markInteraction: () => void
  prepareForRequest: () => void
  resetForThread: (clearWidth: () => void) => void
  reconcileResources: (resources: MothershipResource[], clearWidth: () => void) => void
}

export function useWorkspacePanelController(): WorkspacePanelController {
  const [activeResourceParam, setResourceParam] = useQueryState(resourceParam.key, {
    ...resourceParam.parser,
    ...resourceUrlKeys,
  })
  const setActiveResourceUrl = useCallback<Dispatch<SetStateAction<string | null>>>(
    (action) => {
      if (typeof window !== 'undefined' && window.location.hash) {
        const { pathname, search } = window.location
        window.history.replaceState(window.history.state, '', `${pathname}${search}`)
      }
      void setResourceParam(action)
    },
    [setResourceParam]
  )
  const activeResourceState = useMemo<[string | null, Dispatch<SetStateAction<string | null>>]>(
    () => [activeResourceParam, setActiveResourceUrl],
    [activeResourceParam, setActiveResourceUrl]
  )
  const [isCollapsed, setCollapsed] = useState(true)
  const [skipTransition, setSkipTransition] = useState(false)
  const [activityIds, setActivityIds] = useState<Set<string>>(new Set())
  const collapsedRef = useRef(isCollapsed)
  const activeResourceIdRef = useRef(activeResourceParam)
  const activityIdsRef = useRef(activityIds)
  const transitionFrameRef = useRef<number | null>(null)
  const userOwnsViewRef = useRef(false)
  collapsedRef.current = isCollapsed
  activeResourceIdRef.current = activeResourceParam
  activityIdsRef.current = activityIds

  const notice = useCallback(
    ({ resourceId, activation }: ResourceActivityNotice) => {
      const decision = applyResourceActivityNotice(
        {
          isCollapsed: collapsedRef.current,
          activeResourceId: activeResourceIdRef.current,
          activityIds: activityIdsRef.current,
        },
        { resourceId, activation }
      )

      if (decision.isCollapsed !== collapsedRef.current) setCollapsed(decision.isCollapsed)
      const nextActivityIds = new Set(decision.activityIds)
      activityIdsRef.current = nextActivityIds
      setActivityIds(nextActivityIds)
      if (decision.shouldSelect && decision.activeResourceId !== null) {
        activeResourceIdRef.current = decision.activeResourceId
        setActiveResourceUrl(decision.activeResourceId)
      }
    },
    [setActiveResourceUrl]
  )

  const collapse = useCallback((clearWidth: () => void) => {
    userOwnsViewRef.current = true
    clearWidth()
    setCollapsed(true)
  }, [])
  const expand = useCallback(() => {
    userOwnsViewRef.current = true
    const active = activeResourceIdRef.current
    if (active) {
      setActivityIds((current) => {
        if (!current.has(active)) return current
        const next = new Set(current)
        next.delete(active)
        return next
      })
    }
    setCollapsed(false)
  }, [])
  const select = useCallback((resourceId: string, selectResource: (id: string) => void) => {
    const decision = selectWorkspaceResource(
      {
        activeResourceId: activeResourceIdRef.current,
        activityIds: activityIdsRef.current,
      },
      resourceId
    )
    userOwnsViewRef.current = decision.userOwnsView
    activityIdsRef.current = decision.activityIds
    setActivityIds(decision.activityIds)
    if (!decision.shouldSelect) return
    activeResourceIdRef.current = decision.activeResourceId
    selectResource(decision.activeResourceId)
  }, [])
  const add = useCallback(
    (
      resource: MothershipResource,
      addResource: (resource: MothershipResource) => boolean,
      selectResource: (id: string) => void
    ) => {
      if (!addResource(resource)) return
      userOwnsViewRef.current = true
      select(resource.id, selectResource)
      setCollapsed(false)
    },
    [select]
  )
  const resize = useCallback(
    (
      event: PointerEvent<HTMLDivElement>,
      startResize: (event: PointerEvent<HTMLDivElement>) => void
    ) => {
      userOwnsViewRef.current = true
      startResize(event)
    },
    []
  )
  const markInteraction = useCallback(() => {
    userOwnsViewRef.current = markWorkspacePanelUserOwnership({
      isCollapsed: collapsedRef.current,
      activityIds: activityIdsRef.current,
      userOwnsView: userOwnsViewRef.current,
    }).userOwnsView
  }, [])
  const prepareForRequest = useCallback(() => {
    const next = prepareWorkspacePanelState({
      isCollapsed: collapsedRef.current,
      activityIds: activityIdsRef.current,
      userOwnsView: userOwnsViewRef.current,
    })
    userOwnsViewRef.current = next.userOwnsView
    activityIdsRef.current = next.activityIds
    setActivityIds(next.activityIds)
  }, [])
  const resetForThread = useCallback((clearWidth: () => void) => {
    const next = resetWorkspacePanelState()
    userOwnsViewRef.current = next.userOwnsView
    activityIdsRef.current = next.activityIds
    setActivityIds(next.activityIds)
    clearWidth()
    if (!collapsedRef.current) setCollapsed(next.isCollapsed)
  }, [])
  const reconcileResources = useCallback(
    (resources: MothershipResource[], clearWidth: () => void) => {
      const decision = reconcileWorkspacePanelState(
        {
          isCollapsed: collapsedRef.current,
          activityIds: activityIdsRef.current,
          userOwnsView: userOwnsViewRef.current,
        },
        resources
      )
      if (decision.shouldSkipTransition) {
        setCollapsed(decision.isCollapsed)
        setSkipTransition(true)
        if (transitionFrameRef.current !== null) cancelAnimationFrame(transitionFrameRef.current)
        transitionFrameRef.current = requestAnimationFrame(() => {
          transitionFrameRef.current = null
          setSkipTransition(false)
        })
      } else if (decision.shouldClearWidth) {
        clearWidth()
        setCollapsed(decision.isCollapsed)
      }
      activityIdsRef.current = decision.activityIds
      setActivityIds(decision.activityIds)
    },
    []
  )

  useEffect(
    () => () => {
      if (transitionFrameRef.current !== null) cancelAnimationFrame(transitionFrameRef.current)
    },
    []
  )

  return {
    activeResourceState,
    activeResourceIdRef,
    activityIds,
    isCollapsed,
    skipTransition,
    userOwnsViewRef,
    notice,
    collapse,
    expand,
    select,
    add,
    resize,
    markInteraction,
    prepareForRequest,
    resetForThread,
    reconcileResources,
  }
}

export function useWorkspacePanelSynchronization(
  panel: WorkspacePanelController,
  resources: MothershipResource[],
  clearWidth: () => void
) {
  useEffect(() => {
    panel.reconcileResources(resources, clearWidth)
  }, [panel.reconcileResources, resources, clearWidth])
}
