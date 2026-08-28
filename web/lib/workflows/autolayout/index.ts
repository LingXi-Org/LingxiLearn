export type ExecutionCanvasPosition = { x: number; y: number }

/**
 * Deterministically position the first-party Execution Canvas topology.
 *
 * Returning positions only keeps live execution data out of the topology
 * cache used by the read-only canvas.
 */
export function layoutExecutionCanvasPositions(
  nodeIds: string[],
  connections: Array<{ source: string; target: string }>
): Record<string, ExecutionCanvasPosition> {
  const ranks = new Map(nodeIds.map((id) => [id, 0]))
  for (let pass = 0; pass < nodeIds.length; pass += 1) {
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

  const positions: Record<string, ExecutionCanvasPosition> = {}
  for (const [rank, ids] of byRank) {
    ids.sort()
    ids.forEach((id, index) => {
      positions[id] = { x: rank * 360, y: (index - (ids.length - 1) / 2) * 190 }
    })
  }
  return positions
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
