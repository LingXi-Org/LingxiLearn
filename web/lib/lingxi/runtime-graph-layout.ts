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

const NODE_WIDTH = 250
const COLUMN_GAP = 80
const ROW_GAP = 48
const ROW_HEIGHT = 150

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

  const columns = new Map<number, string[]>()
  for (const id of ids) {
    const rank = ranks.get(id) ?? 0
    columns.set(rank, [...(columns.get(rank) ?? []), id])
  }
  for (const column of columns.values()) {
    column.sort((a, b) => {
      const aStep = Number(blocks[a].data?.step ?? blocks[a].step ?? 0)
      const bStep = Number(blocks[b].data?.step ?? blocks[b].step ?? 0)
      return aStep - bStep || a.localeCompare(b)
    })
  }

  const result: Record<string, RuntimeGraphPosition> = {}
  for (const id of ids) {
    if (previous[id]) result[id] = previous[id]
  }
  for (const [rank, column] of columns) {
    column.forEach((id, index) => {
      if (result[id]) return
      const hint = blocks[id].position
      result[id] = {
        x: rank * (NODE_WIDTH + COLUMN_GAP),
        y: index * (ROW_HEIGHT + ROW_GAP),
      }
      if (hint && typeof hint.x === 'number' && typeof hint.y === 'number' && ids.length === 1) {
        result[id] = { x: hint.x, y: hint.y }
      }
    })
  }
  return result
}
