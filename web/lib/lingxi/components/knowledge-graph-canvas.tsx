'use client'

import { type CSSProperties, useEffect, useMemo, useState } from 'react'
import type { KnowledgeGraphData, KnowledgeGraphNode } from '@/lib/lingxi/types'

interface Point {
  x: number
  y: number
}

export interface KnowledgeGraphMiniNode {
  x: number
  y: number
  hub?: boolean
}

/**
 * The compact landing animation uses the same SVG canvas primitives as the
 * persisted graph viewer.  Keeping this renderer here prevents the hero from
 * growing a second, incompatible knowledge-graph implementation.
 */
export function KnowledgeGraphMiniSvg({
  viewBox,
  nodes,
  edges,
}: {
  viewBox: { width: number; height: number }
  nodes: KnowledgeGraphMiniNode[]
  edges: Array<[number, number]>
}) {
  return (
    <svg
      className='h-[140px] w-full'
      viewBox={`0 0 ${viewBox.width} ${viewBox.height}`}
      fill='none'
      aria-hidden='true'
    >
      <title>embedding graph</title>
      {edges.map(([fromIndex, toIndex], index) => {
        const from = nodes[fromIndex]
        const to = nodes[toIndex]
        if (!from || !to) return null
        return (
          <path
            key={`${fromIndex}-${toIndex}`}
            d={`M ${from.x} ${from.y} L ${to.x} ${to.y}`}
            pathLength={1}
            className='animate-hero-edge-draw [animation-delay:var(--pop-delay)] [stroke-dasharray:1] [stroke-dashoffset:1] motion-reduce:animate-none motion-reduce:[stroke-dashoffset:0]'
            stroke='var(--text-subtle)'
            strokeWidth={0.5}
            style={{ '--pop-delay': `${index * 45}ms` } as CSSProperties}
          />
        )
      })}
      {nodes.map((node, index) => (
        <circle
          key={`${node.x}-${node.y}`}
          cx={node.x}
          cy={node.y}
          r={node.hub ? 3.4 : index % 3 === 0 ? 2.4 : 1.9}
          className={`opacity-0 [transform-box:fill-box] [transform-origin:center] motion-reduce:animate-none motion-reduce:opacity-100 ${
            node.hub
              ? 'animate-[hero-node-pop_440ms_cubic-bezier(0.16,1,0.3,1)_var(--pop-delay)_forwards,hero-graph-pulse_2600ms_ease-in-out_calc(var(--pop-delay)+800ms)_infinite]'
              : 'animate-hero-node-pop [animation-delay:var(--pop-delay)]'
          }`}
          fill={
            node.hub
              ? 'var(--text-primary)'
              : index % 2 === 0
                ? 'var(--text-secondary)'
                : 'var(--text-muted)'
          }
          style={{ '--pop-delay': `${300 + index * 40}ms` } as CSSProperties}
        />
      ))}
    </svg>
  )
}

const stateClass: Record<string, string> = {
  demonstrated: 'fill-emerald-500 stroke-emerald-700',
  emerging: 'fill-sky-400 stroke-sky-700',
  misconception_evidence: 'fill-rose-400 stroke-rose-700',
  needs_recheck: 'fill-amber-400 stroke-amber-700',
  not_observed: 'fill-slate-300 stroke-slate-500',
  unknown: 'fill-slate-200 stroke-slate-400',
}

function layoutGraph(graph: KnowledgeGraphData): Map<string, Point> {
  const positions = new Map<string, Point>()
  const explicitLevels = new Map<string, number>()
  graph.nodes.forEach((node) => {
    if (node.level !== undefined) explicitLevels.set(node.id, node.level)
  })
  const levels = new Map(explicitLevels)
  if (levels.size === 0) {
    const incoming = new Set(graph.edges.filter((edge) => edge.directed).map((edge) => edge.target))
    graph.nodes
      .filter((node) => !incoming.has(node.id))
      .sort((a, b) => b.importance - a.importance || a.id.localeCompare(b.id))
      .forEach((node) => levels.set(node.id, 0))
    for (let pass = 0; pass < graph.nodes.length; pass += 1) {
      let changed = false
      graph.edges
        .filter((edge) => edge.directed)
        .sort((a, b) => a.id.localeCompare(b.id))
        .forEach((edge) => {
          const sourceLevel = levels.get(edge.source)
          if (sourceLevel === undefined) return
          const next = sourceLevel + 1
          if ((levels.get(edge.target) ?? -1) < next) {
            levels.set(edge.target, next)
            changed = true
          }
        })
      if (!changed) break
    }
  }
  const layers = new Map<number, KnowledgeGraphNode[]>()
  graph.nodes.forEach((node) => {
    if (node.position) positions.set(node.id, node.position)
    const level = levels.get(node.id) ?? 0
    const list = layers.get(level) ?? []
    list.push(node)
    layers.set(level, list)
  })
  const maxLevel = Math.max(...Array.from(layers.keys()), 0)
  for (let level = 0; level <= maxLevel; level += 1) {
    const nodes = (layers.get(level) ?? []).sort(
      (a, b) => b.importance - a.importance || a.id.localeCompare(b.id)
    )
    nodes.forEach((node, index) => {
      if (!positions.has(node.id)) {
        positions.set(node.id, {
          x: 100 + (level / Math.max(maxLevel, 1)) * 800,
          y: 90 + ((index + 1) / (nodes.length + 1)) * 420,
        })
      }
    })
  }
  return positions
}

function fitGraph(graph: KnowledgeGraphData): { zoom: number; pan: Point } {
  const positions = layoutGraph(graph)
  const points = graph.nodes
    .map((node) => positions.get(node.id))
    .filter((point): point is Point => Boolean(point))
  if (points.length === 0) return { zoom: 1, pan: { x: 0, y: 0 } }
  const minX = Math.min(...points.map((point) => point.x)) - 55
  const maxX = Math.max(...points.map((point) => point.x)) + 55
  const minY = Math.min(...points.map((point) => point.y)) - 55
  const maxY = Math.max(...points.map((point) => point.y)) + 55
  const width = Math.max(maxX - minX, 1)
  const height = Math.max(maxY - minY, 1)
  const zoom = Math.max(0.6, Math.min(1.8, Math.min(840 / width, 440 / height)))
  return {
    zoom,
    pan: {
      x: zoom * (500 - (minX + maxX) / 2),
      y: zoom * (300 - (minY + maxY) / 2),
    },
  }
}

export function KnowledgeGraphSvg({
  graph,
  zoom = 1,
  pan = { x: 0, y: 0 },
  onSelect,
}: {
  graph: KnowledgeGraphData
  zoom?: number
  pan?: { x: number; y: number }
  onSelect?: (nodeId: string) => void
}) {
  const positions = useMemo(() => layoutGraph(graph), [graph])
  return (
    <svg
      className='h-full w-full select-none'
      viewBox='0 0 1000 600'
      role='img'
      aria-label='Lingxi 知识图谱'
    >
      <defs>
        <marker id='kg-arrow' markerWidth='8' markerHeight='8' refX='7' refY='4' orient='auto'>
          <path d='M0,0 L8,4 L0,8 z' fill='currentColor' />
        </marker>
      </defs>
      <g
        transform={`translate(${pan.x + 500 - 500 * zoom} ${pan.y + 300 - 300 * zoom}) scale(${zoom})`}
      >
        {graph.edges.map((edge) => {
          const source = positions.get(edge.source)
          const target = positions.get(edge.target)
          if (!source || !target) return null
          return (
            <g key={edge.id} className='text-[var(--text-subtle)]'>
              <line
                x1={source.x}
                y1={source.y}
                x2={target.x}
                y2={target.y}
                stroke='currentColor'
                strokeWidth='1.5'
                markerEnd={edge.directed ? 'url(#kg-arrow)' : undefined}
              />
              <text
                x={(source.x + target.x) / 2}
                y={(source.y + target.y) / 2 - 5}
                textAnchor='middle'
                className='fill-current text-[11px]'
              >
                {edge.relation_label}
              </text>
            </g>
          )
        })}
        {graph.nodes.map((node) => {
          const point = positions.get(node.id)
          if (!point) return null
          const radius = 12 + Math.round(Math.max(0, Math.min(1, node.importance)) * 18)
          return (
            <g
              key={node.id}
              transform={`translate(${point.x} ${point.y})`}
              onClick={() => onSelect?.(node.id)}
              className='cursor-pointer'
            >
              {node.is_current && (
                <circle
                  r={radius + 8}
                  className='animate-pulse fill-none stroke-2 stroke-indigo-400'
                />
              )}
              <circle
                r={radius}
                className={`${stateClass[node.learning_state] ?? stateClass.unknown} stroke-2`}
              />
              <text
                y={radius + 18}
                textAnchor='middle'
                className='fill-[var(--text-primary)] text-[12px]'
              >
                {node.label}
              </text>
              <text
                y={radius + 32}
                textAnchor='middle'
                className='fill-[var(--text-muted)] text-[9px]'
              >
                {node.type}
              </text>
            </g>
          )
        })}
      </g>
    </svg>
  )
}

export function KnowledgeGraphCanvas({ graph }: { graph: KnowledgeGraphData }) {
  const initialFit = useMemo(() => fitGraph(graph), [graph])
  const [zoom, setZoom] = useState(initialFit.zoom)
  const [pan, setPan] = useState(initialFit.pan)
  const [selected, setSelected] = useState<string | null>(null)
  const [drag, setDrag] = useState<{ x: number; y: number } | null>(null)
  const selectedNode = graph.nodes.find((node) => node.id === selected)
  useEffect(() => {
    setZoom(initialFit.zoom)
    setPan(initialFit.pan)
    setSelected(null)
  }, [graph.graph_id, graph.revision, initialFit])
  return (
    <div className='flex h-full min-h-[420px] flex-col bg-[var(--surface-1)]'>
      <div className='flex items-center justify-between border-[var(--border-1)] border-b px-4 py-3'>
        <div>
          <h2 className='font-medium text-[var(--text-primary)] text-sm'>{graph.title}</h2>
          <p className='text-[var(--text-muted)] text-xs'>
            {graph.domain || '知识图谱'} · revision {graph.revision}
          </p>
        </div>
        <div className='flex gap-1'>
          <button
            className='rounded border px-2 py-1 text-xs'
            onClick={() => setZoom((value) => Math.max(0.6, value - 0.1))}
          >
            −
          </button>
          <button
            className='rounded border px-2 py-1 text-xs'
            onClick={() => {
              const fit = fitGraph(graph)
              setZoom(fit.zoom)
              setPan(fit.pan)
            }}
          >
            适配
          </button>
          <button
            className='rounded border px-2 py-1 text-xs'
            onClick={() => setZoom((value) => Math.min(1.8, value + 0.1))}
          >
            ＋
          </button>
        </div>
      </div>
      <div
        className='relative flex-1 cursor-grab overflow-hidden active:cursor-grabbing'
        onPointerDown={(event) => {
          event.currentTarget.setPointerCapture(event.pointerId)
          setDrag({ x: event.clientX - pan.x, y: event.clientY - pan.y })
        }}
        onPointerMove={(event) => {
          if (drag) setPan({ x: event.clientX - drag.x, y: event.clientY - drag.y })
        }}
        onPointerUp={() => setDrag(null)}
        onPointerCancel={() => setDrag(null)}
        onWheel={(event) => {
          event.preventDefault()
          setZoom((value) => Math.max(0.6, Math.min(1.8, value - event.deltaY * 0.001)))
        }}
      >
        <KnowledgeGraphSvg graph={graph} zoom={zoom} pan={pan} onSelect={setSelected} />
        {selectedNode && (
          <aside className='absolute top-3 right-3 w-56 rounded-lg border border-[var(--border-1)] bg-[var(--surface-1)]/95 p-3 shadow-lg'>
            <div className='flex items-start justify-between gap-2'>
              <strong className='text-sm'>{selectedNode.label}</strong>
              <button onClick={() => setSelected(null)} aria-label='关闭'>
                ×
              </button>
            </div>
            <p className='mt-2 text-[var(--text-muted)] text-xs'>类型：{selectedNode.type}</p>
            <p className='text-[var(--text-muted)] text-xs'>
              学习状态：{selectedNode.learning_state}
            </p>
            {selectedNode.description && (
              <p className='mt-2 text-[var(--text-secondary)] text-xs'>
                {selectedNode.description}
              </p>
            )}
          </aside>
        )}
      </div>
    </div>
  )
}
