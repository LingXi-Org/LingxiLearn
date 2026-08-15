export interface RuntimeGraphBlock {
  id?: string
  name?: string
  rows?: unknown[]
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

export const RUNTIME_GRAPH_CANVAS = { width: 760, height: 700 } as const
export const RUNTIME_GRAPH_NODE_WIDTH = 360
const NODE_MIN_HEIGHT = 76
const NODE_GAP_X = 52
const NODE_GAP_Y = 108
const CANVAS_PADDING = 48

function blockHeight(block: RuntimeGraphBlock): number {
  const rows = Array.isArray(block.rows) ? block.rows.length : 0
  return Math.max(NODE_MIN_HEIGHT, 40 + (rows > 0 ? 16 + rows * 21 + (rows - 1) * 8 : 0))
}

function blockOrder(blocks: Record<string, RuntimeGraphBlock>, id: string): [number, string] {
  return [Number(blocks[id]?.data?.step ?? blocks[id]?.step ?? 0), id]
}

function compareIds(blocks: Record<string, RuntimeGraphBlock>, a: string, b: string): number {
  const [aStep, aId] = blockOrder(blocks, a)
  const [bStep, bId] = blockOrder(blocks, b)
  return aStep - bStep || aId.localeCompare(bId)
}

function stronglyConnectedComponents(ids: string[], outgoing: Map<string, string[]>): string[][] {
  let nextIndex = 0
  const index = new Map<string, number>()
  const lowLink = new Map<string, number>()
  const stack: string[] = []
  const onStack = new Set<string>()
  const result: string[][] = []

  const visit = (id: string) => {
    index.set(id, nextIndex)
    lowLink.set(id, nextIndex)
    nextIndex += 1
    stack.push(id)
    onStack.add(id)
    for (const target of outgoing.get(id) ?? []) {
      if (!index.has(target)) {
        visit(target)
        lowLink.set(id, Math.min(lowLink.get(id)!, lowLink.get(target)!))
      } else if (onStack.has(target)) {
        lowLink.set(id, Math.min(lowLink.get(id)!, index.get(target)!))
      }
    }
    if (lowLink.get(id) !== index.get(id)) return
    const component: string[] = []
    let member = ''
    do {
      member = stack.pop()!
      onStack.delete(member)
      component.push(member)
    } while (member !== id)
    result.push(component)
  }

  ids.forEach((id) => {
    if (!index.has(id)) visit(id)
  })
  return result
}

interface LayeredComponent {
  ids: string[]
  rank: number
}

/**
 * Layered topology layout used by the live runtime graph.
 *
 * The runtime graph is read as a dependency DAG after SCCs are collapsed.
 * Every rank is a horizontal lane, so handles can stay strictly on the top
 * and bottom of cards while a source fans out to any number of parallel
 * targets in the next lanes.
 */
export function layoutRuntimeGraph(
  blocks: Record<string, RuntimeGraphBlock>,
  edges: RuntimeGraphEdge[],
  previous: Record<string, RuntimeGraphPosition> = {}
): Record<string, RuntimeGraphPosition> {
  const ids = Object.keys(blocks).sort((a, b) => compareIds(blocks, a, b))
  if (ids.length === 0) return {}

  const outgoing = new Map(ids.map((id) => [id, [] as string[]]))
  const incoming = new Map(ids.map((id) => [id, [] as string[]]))
  for (const edge of edges) {
    if (outgoing.has(edge.source) && incoming.has(edge.target) && edge.source !== edge.target) {
      outgoing.get(edge.source)!.push(edge.target)
      incoming.get(edge.target)!.push(edge.source)
    }
  }

  const sccs = stronglyConnectedComponents(ids, outgoing)
  const sccByNode = new Map<string, number>()
  sccs.forEach((members, index) => members.forEach((id) => sccByNode.set(id, index)))
  const condensed = new Map<number, Set<number>>()
  const condensedIncoming = new Map<number, Set<number>>()
  sccs.forEach((_, index) => {
    condensed.set(index, new Set())
    condensedIncoming.set(index, new Set())
  })
  for (const [source, targets] of outgoing) {
    for (const target of targets) {
      const from = sccByNode.get(source)!
      const to = sccByNode.get(target)!
      if (from === to) continue
      condensed.get(from)!.add(to)
      condensedIncoming.get(to)!.add(from)
    }
  }

  const firstNode = (scc: number) => [...sccs[scc]].sort((a, b) => compareIds(blocks, a, b))[0]
  const indegree = new Map<number, number>(
    [...condensedIncoming].map(([scc, parents]) => [scc, parents.size])
  )
  const queue = [...indegree]
    .filter(([, degree]) => degree === 0)
    .map(([scc]) => scc)
    .sort((a, b) => compareIds(blocks, firstNode(a), firstNode(b)))
  const rank = new Map<number, number>()
  queue.forEach((scc) => rank.set(scc, 0))
  for (let cursor = 0; cursor < queue.length; cursor += 1) {
    const source = queue[cursor]
    for (const target of condensed.get(source) ?? []) {
      rank.set(target, Math.max(rank.get(target) ?? 0, (rank.get(source) ?? 0) + 1))
      indegree.set(target, indegree.get(target)! - 1)
      if (indegree.get(target) === 0) queue.push(target)
    }
  }
  // This is only reachable for malformed cyclic condensation data; keeping a
  // deterministic fallback prevents a node from disappearing from the graph.
  sccs.forEach((_, scc) => {
    if (!rank.has(scc)) rank.set(scc, 0)
  })

  const layers = new Map<number, LayeredComponent[]>()
  sccs.forEach((members, scc) => {
    const layer = rank.get(scc) ?? 0
    const component: LayeredComponent = {
      ids: [...members].sort((a, b) => compareIds(blocks, a, b)),
      rank: layer,
    }
    layers.set(layer, [...(layers.get(layer) ?? []), component])
  })

  const result: Record<string, RuntimeGraphPosition> = {}
  const layerNumbers = [...layers.keys()].sort((a, b) => a - b)
  let y = CANVAS_PADDING
  let maxWidth = 0
  layerNumbers.forEach((layerNumber) => {
    const layer = layers.get(layerNumber)!
    const layerIds = layer.flatMap((component) => component.ids)
    layerIds.sort((a, b) => {
      const previousDelta =
        (previous[a]?.x ?? Number.POSITIVE_INFINITY) - (previous[b]?.x ?? Number.POSITIVE_INFINITY)
      return Number.isFinite(previousDelta) && previousDelta !== 0
        ? previousDelta
        : compareIds(blocks, a, b)
    })
    const layerWidth = Math.max(
      RUNTIME_GRAPH_NODE_WIDTH,
      layerIds.length * RUNTIME_GRAPH_NODE_WIDTH + Math.max(0, layerIds.length - 1) * NODE_GAP_X
    )
    const maxHeight = Math.max(...layerIds.map((id) => blockHeight(blocks[id])))
    const startX = CANVAS_PADDING
    layerIds.forEach((id, index) => {
      result[id] = {
        x: startX + index * (RUNTIME_GRAPH_NODE_WIDTH + NODE_GAP_X),
        y,
      }
    })
    maxWidth = Math.max(maxWidth, layerWidth)
    y += maxHeight + NODE_GAP_Y
  })

  // Keep the result rooted in the same coordinate system as the canvas even
  // when a graph has only one layer or contains disconnected components.
  void maxWidth
  return result
}
