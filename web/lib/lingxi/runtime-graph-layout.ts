export interface RuntimeGraphBlock {
  id?: string
  name?: string
  position?: { x?: number; y?: number }
  data?: { step?: number; planTaskId?: string; [key: string]: unknown }
  step?: number
}

export interface RuntimeGraphEdge {
  id: string
  source: string
  target: string
}

export interface RuntimeGraphPosition {
  x: number
  y: number
}

/** These are the homepage workflow stage's design-space dimensions. */
export const RUNTIME_GRAPH_CANVAS = { width: 560, height: 700 } as const
export const RUNTIME_GRAPH_NODE_WIDTH = 250
const LANE_X = [0, 155, 310]
const VERTICAL_GAP = 80

function blockHeight(block: RuntimeGraphBlock): number {
  const rows = Array.isArray((block as Record<string, unknown>).rows)
    ? ((block as Record<string, unknown>).rows as unknown[]).length
    : 0
  return 40 + (rows > 0 ? 16 + rows * 21 + (rows - 1) * 8 : 0)
}

/** Deterministic layered layout. Existing positions win so late nodes do not move the run. */
export function layoutRuntimeGraph(
  blocks: Record<string, RuntimeGraphBlock>,
  edges: RuntimeGraphEdge[],
  previous: Record<string, RuntimeGraphPosition> = {}
): Record<string, RuntimeGraphPosition> {
  const ids = Object.keys(blocks).sort()
  const incoming = new Map(ids.map((id) => [id, [] as string[]]))
  for (const edge of edges) {
    if (incoming.has(edge.target) && incoming.has(edge.source)) incoming.get(edge.target)!.push(edge.source)
  }
  const ranks = new Map<string, number>()
  const visiting = new Set<string>()
  const rankOf = (id: string): number => {
    const cached = ranks.get(id)
    if (cached !== undefined) return cached
    if (visiting.has(id)) return 0
    visiting.add(id)
    const rank = Math.max(0, ...(incoming.get(id) ?? []).map(rankOf).map((value) => value + 1))
    visiting.delete(id)
    ranks.set(id, rank)
    return rank
  }
  ids.forEach(rankOf)

  const layers = new Map<number, string[]>()
  for (const id of ids) {
    const rank = ranks.get(id) ?? 0
    layers.set(rank, [...(layers.get(rank) ?? []), id])
  }
  for (const layer of layers.values()) {
    layer.sort((a, b) => {
      const aStep = Number(blocks[a].data?.step ?? blocks[a].step ?? 0)
      const bStep = Number(blocks[b].data?.step ?? blocks[b].step ?? 0)
      return aStep - bStep || a.localeCompare(b)
    })
  }

  const result: Record<string, RuntimeGraphPosition> = {}
  for (const id of ids) {
    if (previous[id]) result[id] = previous[id]
  }
  for (const [rank, layer] of layers) {
    const layerHasParallelNodes = layer.length > 1
    layer.forEach((id, index) => {
      if (result[id]) return
      const hint = blocks[id].position

      // New nodes are placed below their latest dependency. This produces the
      // homepage's vertical flow while preserving an already rendered node's
      // position when a late SSE event adds another primitive.
      const predecessors = incoming.get(id) ?? []
      const dependencyBottom = predecessors.reduce(
        (bottom, predecessor) => {
          const position = result[predecessor] ?? previous[predecessor]
          return position
            ? Math.max(bottom, position.y + blockHeight(blocks[predecessor]))
            : bottom
        },
        12 - VERTICAL_GAP
      )
      const x = layerHasParallelNodes
        ? LANE_X[index % LANE_X.length] ?? index * (RUNTIME_GRAPH_NODE_WIDTH + 60)
        : LANE_X[1]
      result[id] = { x, y: Math.max(12, dependencyBottom + VERTICAL_GAP) }

      // A backend position is only a first-load hint for a lone node. Once a
      // graph has dependencies, the stable stage layout is the source of truth.
      if (hint && typeof hint.x === 'number' && typeof hint.y === 'number' && ids.length === 1) {
        result[id] = { x: hint.x, y: hint.y }
      }
    })
  }
  return result
}
