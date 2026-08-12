"use client";

import { useMemo } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
  type Node,
  type NodeTypes,
} from "@xyflow/react";
import type { AgentCanvasGraph } from "@/lib/sim-adapter";
import { SimWorkflowBlock, type SimWorkflowBlockData, colorByStatus } from "./workflow-block";

const nodeTypes: NodeTypes = { workflowBlock: SimWorkflowBlock };

function layoutGraph(graph: AgentCanvasGraph, onNodeSelect?: (id: string) => void) {
  // Layout is derived from the graph supplied by the live task. Nothing is
  // mounted until the coordinator has produced nodes, so future LingxiGraph
  // topologies can render without changing this Sim canvas shell.
  const levels = new Map<string, number>(graph.nodes.map((node) => [node.id, 0]));
  for (let pass = 0; pass < graph.nodes.length; pass += 1) {
    let changed = false;
    for (const edge of graph.edges) {
      const next = (levels.get(edge.from) ?? 0) + 1;
      if (next > (levels.get(edge.to) ?? 0)) {
        levels.set(edge.to, next);
        changed = true;
      }
    }
    if (!changed) break;
  }
  const byLevel = new Map<number, typeof graph.nodes>();
  for (const node of graph.nodes) {
    const level = levels.get(node.id) ?? 0;
    byLevel.set(level, [...(byLevel.get(level) ?? []), node]);
  }
  const nodes: Node<SimWorkflowBlockData>[] = graph.nodes.map((node) => {
    const level = levels.get(node.id) ?? 0;
    const peers = byLevel.get(level) ?? [node];
    const index = peers.findIndex((peer) => peer.id === node.id);
    return {
      id: node.id,
      type: "workflowBlock",
      position: { x: (index - (peers.length - 1) / 2) * 315, y: level * 150 },
      data: { label: node.label, kind: node.kind, status: node.status, detail: node.detail, nodeId: node.id, onSelect: onNodeSelect },
    };
  });
  const edges: Edge[] = graph.edges.map((edge, index) => ({
    id: `${edge.from}-${edge.to}-${index}`,
    source: edge.from,
    target: edge.to,
    type: "smoothstep",
    label: edge.label,
    labelStyle: { fill: "var(--text-muted)", fontSize: 10 },
    labelBgStyle: { fill: "var(--surface-1)", fillOpacity: 0.9 },
    style: { stroke: "var(--workflow-edge, #c8c8c8)", strokeWidth: 2 },
  }));
  return { nodes, edges };
}

export function SimWorkflowCanvas({ graph, onNodeSelect }: { graph: AgentCanvasGraph; onNodeSelect?: (id: string) => void }) {
  const flow = useMemo(() => layoutGraph(graph, onNodeSelect), [graph, onNodeSelect]);
  return (
    <ReactFlowProvider>
      <ReactFlow
        nodes={flow.nodes}
        edges={flow.edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.22, maxZoom: 1 }}
        minZoom={0.3}
        maxZoom={1.35}
        nodesConnectable={false}
        nodesFocusable={false}
        edgesFocusable={false}
        elementsSelectable={false}
        panOnScroll
        proOptions={{ hideAttribution: true }}
        className="bg-[var(--surface-1)] [&_.react-flow__pane]:cursor-grab [&_.react-flow__pane:active]:cursor-grabbing"
      >
        <Background color="var(--border)" gap={22} size={1} />
        <Controls showInteractive={false} />
        <MiniMap nodeColor={(node) => colorByStatus[(node.data as SimWorkflowBlockData).status]} maskColor="rgb(248 248 248 / 0.7)" />
      </ReactFlow>
    </ReactFlowProvider>
  );
}
