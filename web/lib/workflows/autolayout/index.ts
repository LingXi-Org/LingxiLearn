import type { ExecutionCanvasNode } from '@/lib/lingxi/runtime-graph-adapter'

/**
 * Deterministically position the first-party Execution Canvas view model.
 *
 * This deliberately consumes native canvas nodes rather than adapting an
 * execution snapshot into the editable WorkflowState contract.
 */
export function layoutExecutionCanvas(
  nodes: Record<string, ExecutionCanvasNode>,
  connections: Array<{ source: string; target: string }>
): Record<string, ExecutionCanvasNode> {
  const ranks = new Map(Object.keys(nodes).map((id) => [id, 0]))
  for (let pass = 0; pass < Object.keys(nodes).length; pass += 1) {
    let changed = false
    for (const connection of connections) {
      const sourceRank = ranks.get(connection.source)
      const targetRank = ranks.get(connection.target)
      if (sourceRank === undefined || targetRank === undefined || sourceRank + 1 <= targetRank) {
        continue
      }
      ranks.set(connection.target, sourceRank + 1)
      changed = true
    }
    if (!changed) break
  }

  const byRank = new Map<number, string[]>()
  for (const [id, rank] of ranks) {
    byRank.set(rank, [...(byRank.get(rank) ?? []), id])
  }

  const positioned = { ...nodes }
  for (const [rank, ids] of byRank) {
    ids.sort()
    ids.forEach((id, index) => {
      positioned[id] = {
        ...nodes[id],
        position: { x: rank * 360, y: (index - (ids.length - 1) / 2) * 190 },
      }
    })
  }
  return positioned
}

export {
  getTargetedLayoutChangeSet,
  getTargetedLayoutImpact,
} from '@/lib/workflows/autolayout/change-set'
export { applyTargetedLayout } from '@/lib/workflows/autolayout/targeted'
export type { Edge, LayoutOptions, LayoutResult } from '@/lib/workflows/autolayout/types'
export {
  getBlockMetrics,
  isContainerType,
  shouldSkipAutoLayout,
  snapPositionToGrid,
  transferBlockHeights,
} from '@/lib/workflows/autolayout/utils'
