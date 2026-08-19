/**
 * Knowledge detail document/chunk domain primitives.
 *
 * Pure projections over the document list (base detail) and chunk list
 * (document detail) shared by the command layer so bulk semantics live in one
 * tested place instead of being re-derived per handler.
 */

/** Anything the detail lists can select and enable/disable. */
export interface SelectableResource {
  id: string
  enabled: boolean
}

export type BulkOperation = 'enable' | 'disable' | 'delete'

/**
 * Resolve which selected resources a bulk operation actually mutates. Enable
 * only targets disabled rows and disable only enabled rows (a no-op selection
 * must not hit the API); delete targets every selected row.
 */
export function resolveBulkTargets<T extends SelectableResource>(
  resources: readonly T[],
  selectedIds: ReadonlySet<string>,
  operation: BulkOperation
): T[] {
  const selected = resources.filter((resource) => selectedIds.has(resource.id))
  switch (operation) {
    case 'enable':
      return selected.filter((resource) => !resource.enabled)
    case 'disable':
      return selected.filter((resource) => resource.enabled)
    case 'delete':
      return selected
  }
}

/**
 * Enabled/disabled tallies inside the selection — drives the ActionBar and the
 * context-menu toggle label. (Select-all-across-pages mode is resolved by the
 * caller from the pagination total, which the domain cannot see.)
 */
export function countSelectedByEnabled<T extends SelectableResource>(
  resources: readonly T[],
  selectedIds: ReadonlySet<string>
): { enabled: number; disabled: number } {
  let enabled = 0
  let disabled = 0
  for (const resource of resources) {
    if (!selectedIds.has(resource.id)) continue
    if (resource.enabled) {
      enabled += 1
    } else {
      disabled += 1
    }
  }
  return { enabled, disabled }
}

/** Whether every listed resource is selected (drives the header checkbox). */
export function isEntirePageSelected(
  resourceCount: number,
  selectedIds: ReadonlySet<string>
): boolean {
  return resourceCount > 0 && selectedIds.size === resourceCount
}
