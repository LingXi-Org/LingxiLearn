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

export const RUNTIME_GRAPH_CANVAS = { width: 560, height: 700 } as const
export const RUNTIME_GRAPH_NODE_WIDTH = 250
const NODE_MIN_HEIGHT = 76
const NODE_GAP = 72
const COMPONENT_GAP = 180
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

/** Tarjan SCC keeps loops together before the graph is expanded into radial shells. */
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
    let member: string
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

interface ComponentLayout {
  positions: Record<string, RuntimeGraphPosition>
  width: number
  height: number
}

function layoutConnectedComponent(
  nodeIds: string[],
  blocks: Record<string, RuntimeGraphBlock>,
  outgoing: Map<string, string[]>,
  incoming: Map<string, string[]>
): ComponentLayout {
  const nodeSet = new Set(nodeIds)
  const sccs = stronglyConnectedComponents(nodeIds, outgoing)
  const sccByNode = new Map<string, number>()
  sccs.forEach((members, scc) => members.forEach((id) => sccByNode.set(id, scc)))

  const condensed = new Map<number, Set<number>>(sccs.map((_, index) => [index, new Set()]))
  const condensedIncoming = new Map<number, Set<number>>(sccs.map((_, index) => [index, new Set()]))
  for (const source of nodeIds) {
    for (const target of outgoing.get(source) ?? []) {
      if (!nodeSet.has(target)) continue
      const from = sccByNode.get(source)!
      const to = sccByNode.get(target)!
      if (from === to) continue
      condensed.get(from)!.add(to)
      condensedIncoming.get(to)!.add(from)
    }
  }

  const sccOrder = (scc: number) =>
    [...sccs[scc]].sort((a, b) => compareIds(blocks, a, b))[0]
  const roots = sccs
    .map((_, index) => index)
    .filter((index) => condensedIncoming.get(index)!.size === 0)
    .sort((a, b) => compareIds(blocks, sccOrder(a), sccOrder(b)))
  const root = roots[0] ?? 0

  // Use undirected distance from the most meaningful root. Direction remains
  // encoded by the edges, while shells are free to occupy all four quadrants.
  const neighbors = new Map<number, Set<number>>(sccs.map((_, index) => [index, new Set()]))
  condensed.forEach((targets, source) => targets.forEach((target) => {
    neighbors.get(source)!.add(target)
    neighbors.get(target)!.add(source)
  }))
  const level = new Map<number, number>([[root, 0]])
  const queue = [root]
  for (let cursor = 0; cursor < queue.length; cursor += 1) {
    const current = queue[cursor]
    const ordered = [...neighbors.get(current)!].sort((a, b) =>
      compareIds(blocks, sccOrder(a), sccOrder(b))
    )
    for (const neighbor of ordered) {
      if (level.has(neighbor)) continue
      level.set(neighbor, level.get(current)! + 1)
      queue.push(neighbor)
    }
  }

  const shells = new Map<number, string[]>()
  sccs.forEach((members, scc) => {
    const shell = level.get(scc) ?? 0
    const sorted = [...members].sort((a, b) => compareIds(blocks, a, b))
    shells.set(shell, [...(shells.get(shell) ?? []), ...sorted])
  })
  shells.forEach((members) => members.sort((a, b) => compareIds(blocks, a, b)))

  const centers: Record<string, RuntimeGraphPosition> = {}
  let previousRadius = 0
  const shellNumbers = [...shells.keys()].sort((a, b) => a - b)
  for (const shell of shellNumbers) {
    const members = shells.get(shell)!
    const maxHeight = Math.max(...members.map((id) => blockHeight(blocks[id])))
    const footprint = Math.hypot(RUNTIME_GRAPH_NODE_WIDTH, maxHeight) + NODE_GAP
    if (shell === 0 && members.length === 1) {
      centers[members[0]] = { x: 0, y: 0 }
      previousRadius = footprint / 2
      continue
    }
    const collisionRadius = members.length > 1
      ? footprint / (2 * Math.sin(Math.PI / members.length))
      : 0
    const radius = Math.max(previousRadius + footprint, collisionRadius)
    const angleOffset = -Math.PI / 2 + shell * 0.43
    members.forEach((id, index) => {
      const angle = angleOffset + (2 * Math.PI * index) / members.length
      centers[id] = { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius }
    })
    previousRadius = radius
  }

  let minX = Number.POSITIVE_INFINITY
  let minY = Number.POSITIVE_INFINITY
  let maxX = Number.NEGATIVE_INFINITY
  let maxY = Number.NEGATIVE_INFINITY
  nodeIds.forEach((id) => {
    const center = centers[id]
    const height = blockHeight(blocks[id])
    minX = Math.min(minX, center.x - RUNTIME_GRAPH_NODE_WIDTH / 2)
    minY = Math.min(minY, center.y - height / 2)
    maxX = Math.max(maxX, center.x + RUNTIME_GRAPH_NODE_WIDTH / 2)
    maxY = Math.max(maxY, center.y + height / 2)
  })

  const positions: Record<string, RuntimeGraphPosition> = {}
  nodeIds.forEach((id) => {
    positions[id] = {
      x: centers[id].x - RUNTIME_GRAPH_NODE_WIDTH / 2 - minX,
      y: centers[id].y - blockHeight(blocks[id]) / 2 - minY,
    }
  })
  return { positions, width: maxX - minX, height: maxY - minY }
}

/**
 * Deterministic all-direction topology layout.
 *
 * Cycles are collapsed with SCC, connected components are expanded into radial
 * shells, and component bounds are packed into rows. Ring radii are calculated
 * from the real card footprint, so cards cannot overlap even as the graph grows.
 */
export function layoutRuntimeGraph(
  blocks: Record<string, RuntimeGraphBlock>,
  edges: RuntimeGraphEdge[],
  _previous: Record<string, RuntimeGraphPosition> = {}
): Record<string, RuntimeGraphPosition> {
  const ids = Object.keys(blocks).sort((a, b) => compareIds(blocks, a, b))
  if (ids.length === 0) return {}

  const outgoing = new Map(ids.map((id) => [id, [] as string[]]))
  const incoming = new Map(ids.map((id) => [id, [] as string[]]))
  for (const edge of edges) {
    if (!outgoing.has(edge.source) || !incoming.has(edge.target)) continue
    outgoing.get(edge.source)!.push(edge.target)
    incoming.get(edge.target)!.push(edge.source)
  }

  const unseen = new Set(ids)
  const components: string[][] = []
  while (unseen.size > 0) {
    const start = [...unseen].sort((a, b) => compareIds(blocks, a, b))[0]
    const component: string[] = []
    const queue = [start]
    unseen.delete(start)
    for (let cursor = 0; cursor < queue.length; cursor += 1) {
      const id = queue[cursor]
      component.push(id)
      const adjacent = [...(outgoing.get(id) ?? []), ...(incoming.get(id) ?? [])]
        .sort((a, b) => compareIds(blocks, a, b))
      for (const neighbor of adjacent) {
        if (!unseen.delete(neighbor)) continue
        queue.push(neighbor)
      }
    }
    components.push(component)
  }

  const layouts = components.map((component) =>
    layoutConnectedComponent(component, blocks, outgoing, incoming)
  )
  const totalArea = layouts.reduce(
    (area, layout) => area + (layout.width + COMPONENT_GAP) * (layout.height + COMPONENT_GAP),
    0
  )
  const targetRowWidth = Math.max(560, Math.sqrt(totalArea) * 1.35)
  const result: Record<string, RuntimeGraphPosition> = {}
  let cursorX = CANVAS_PADDING
  let cursorY = CANVAS_PADDING
  let rowHeight = 0

  layouts.forEach((layout) => {
    if (cursorX > CANVAS_PADDING && cursorX + layout.width > targetRowWidth) {
      cursorX = CANVAS_PADDING
      cursorY += rowHeight + COMPONENT_GAP
      rowHeight = 0
    }
    Object.entries(layout.positions).forEach(([id, position]) => {
      result[id] = { x: position.x + cursorX, y: position.y + cursorY }
    })
    cursorX += layout.width + COMPONENT_GAP
    rowHeight = Math.max(rowHeight, layout.height)
  })

  return result
}
