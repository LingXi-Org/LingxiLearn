import { describe, expect, it } from 'vitest'
import {
  applyResourceActivityNotice,
  markWorkspacePanelUserOwnership,
  prepareWorkspacePanelState,
  reconcileWorkspacePanelState,
  resetWorkspacePanelState,
  selectWorkspaceResource,
  type WorkspacePanelResourceState,
  type WorkspacePanelViewState,
} from './use-workspace-panel-controller'

function resourceState(
  overrides: Partial<WorkspacePanelResourceState> = {}
): WorkspacePanelResourceState {
  return {
    isCollapsed: true,
    activeResourceId: null,
    activityIds: new Set(),
    ...overrides,
  }
}

function viewState(overrides: Partial<WorkspacePanelViewState> = {}): WorkspacePanelViewState {
  return {
    isCollapsed: true,
    activityIds: new Set(),
    userOwnsView: false,
    ...overrides,
  }
}

describe('resource activity notices', () => {
  it('clears a marker without opening or changing the selected resource', () => {
    const decision = applyResourceActivityNotice(
      resourceState({
        isCollapsed: false,
        activeResourceId: 'resource-a',
        activityIds: new Set(['resource-b']),
      }),
      { resourceId: 'resource-b', activation: 'clear' }
    )

    expect(decision).toMatchObject({
      isCollapsed: false,
      activeResourceId: 'resource-a',
      shouldSelect: false,
    })
    expect(decision.activityIds).toEqual(new Set())
  })

  it('highlights background activity while another resource is selected', () => {
    const decision = applyResourceActivityNotice(
      resourceState({
        activeResourceId: 'resource-a',
        activityIds: new Set(['resource-c']),
      }),
      { resourceId: 'resource-b', activation: 'activity' }
    )

    expect(decision).toMatchObject({
      isCollapsed: false,
      activeResourceId: 'resource-a',
      shouldSelect: false,
    })
    expect(decision.activityIds).toEqual(new Set(['resource-c', 'resource-b']))
  })

  it('selects the first active resource when there is no current selection', () => {
    const decision = applyResourceActivityNotice(
      resourceState(),
      { resourceId: 'resource-a', activation: 'activity' }
    )

    expect(decision).toMatchObject({
      isCollapsed: false,
      activeResourceId: 'resource-a',
      shouldSelect: true,
    })
    expect(decision.activityIds).toEqual(new Set())
  })

  it('reveals a background resource without stealing the active selection', () => {
    const decision = applyResourceActivityNotice(
      resourceState({
        isCollapsed: true,
        activeResourceId: 'resource-a',
        activityIds: new Set(['resource-b']),
      }),
      { resourceId: 'resource-b', activation: 'reveal' }
    )

    expect(decision).toMatchObject({
      isCollapsed: false,
      activeResourceId: 'resource-a',
      shouldSelect: false,
    })
    expect(decision.activityIds).toEqual(new Set(['resource-b']))
  })

  it('consumes a stale marker when activity belongs to the active resource', () => {
    const decision = applyResourceActivityNotice(
      resourceState({
        isCollapsed: false,
        activeResourceId: 'resource-a',
        activityIds: new Set(['resource-a']),
      }),
      { resourceId: 'resource-a', activation: 'activity' }
    )

    expect(decision.shouldSelect).toBe(false)
    expect(decision.activityIds).toEqual(new Set())
  })
})

describe('resource selection', () => {
  it('takes ownership, consumes its marker, and requests a URL update when changed', () => {
    const decision = selectWorkspaceResource(
      { activeResourceId: 'resource-a', activityIds: new Set(['resource-b']) },
      'resource-b'
    )

    expect(decision).toEqual({
      activeResourceId: 'resource-b',
      activityIds: new Set(),
      userOwnsView: true,
      shouldSelect: true,
    })
  })

  it('still takes ownership but avoids a redundant URL update when already active', () => {
    const decision = selectWorkspaceResource(
      { activeResourceId: 'resource-a', activityIds: new Set(['resource-a']) },
      'resource-a'
    )

    expect(decision).toEqual({
      activeResourceId: 'resource-a',
      activityIds: new Set(),
      userOwnsView: true,
      shouldSelect: false,
    })
  })
})

describe('resource reconciliation', () => {
  it('automatically reveals resources for a fresh view and prunes stale markers', () => {
    const state = viewState({ activityIds: new Set(['resource-a', 'stale']) })
    const decision = reconcileWorkspacePanelState(state, [{ id: 'resource-a' }])

    expect(decision).toMatchObject({
      isCollapsed: false,
      userOwnsView: false,
      shouldClearWidth: false,
      shouldSkipTransition: true,
    })
    expect(decision.activityIds).toEqual(new Set(['resource-a']))
    expect(state.activityIds).toEqual(new Set(['resource-a', 'stale']))
  })

  it('does not auto-reveal after the user has taken ownership of a collapsed view', () => {
    const decision = reconcileWorkspacePanelState(
      viewState({ userOwnsView: true }),
      [{ id: 'resource-a' }]
    )

    expect(decision).toMatchObject({
      isCollapsed: true,
      userOwnsView: true,
      shouldClearWidth: false,
      shouldSkipTransition: false,
    })
  })

  it('collapses and clears the imperative width when the last resource disappears', () => {
    const decision = reconcileWorkspacePanelState(
      viewState({ isCollapsed: false, activityIds: new Set(['resource-a']) }),
      []
    )

    expect(decision).toMatchObject({
      isCollapsed: true,
      shouldClearWidth: true,
      shouldSkipTransition: false,
    })
    expect(decision.activityIds).toEqual(new Set())
  })
})

describe('thread boundaries and ownership', () => {
  it('clears transient activity before a request but preserves the current collapse state', () => {
    const decision = prepareWorkspacePanelState(
      viewState({ isCollapsed: false, activityIds: new Set(['resource-a']), userOwnsView: true })
    )

    expect(decision).toEqual({
      isCollapsed: false,
      activityIds: new Set(),
      userOwnsView: false,
    })
  })

  it('resets the panel for a new thread', () => {
    expect(resetWorkspacePanelState()).toEqual({
      isCollapsed: true,
      activityIds: new Set(),
      userOwnsView: false,
    })
  })

  it('records explicit panel interaction as user ownership without changing markers', () => {
    const decision = markWorkspacePanelUserOwnership(
      viewState({ activityIds: new Set(['resource-a']) })
    )

    expect(decision).toEqual({
      isCollapsed: true,
      activityIds: new Set(['resource-a']),
      userOwnsView: true,
    })
  })
})
