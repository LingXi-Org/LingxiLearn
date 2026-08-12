"use client";

import { memo, useMemo, type ComponentType } from "react";
import {
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
  type Node,
  type NodeProps,
  type NodeTypes,
} from "@xyflow/react";
import { Bot, Check, GitBranch, Merge, Play, Sparkles, Timer, X } from "lucide-react";
import type { AgentCanvasGraph, AgentCanvasNodeKind, AgentCanvasStatus } from "@/lib/sim-adapter";

type WorkflowNodeData = {
  label: string;
  kind: AgentCanvasNodeKind;
  status: AgentCanvasStatus;
  detail: string;
  nodeId: string;
  onSelect?: (id: string) => void;
};

const iconByKind: Record<AgentCanvasNodeKind, ComponentType<{ className?: string }>> = {
  input: Play,
  intent: Sparkles,
  agent: Bot,
  merge: Merge,
};

const colorByStatus: Record<AgentCanvasStatus, string> = {
  pending: "#a3a3a3",
  running: "#7f77dd",
  complete: "#1d9e75",
  error: "#d85a30",
};

const labelByStatus: Record<AgentCanvasStatus, string> = {
  pending: "等待",
  running: "执行中",
  complete: "完成",
  error: "失败",
};

const WorkflowBlock = memo(function WorkflowBlock({ data }: NodeProps<Node<WorkflowNodeData>>) {
  const Icon = iconByKind[data.kind] ?? GitBranch;
  const statusColor = colorByStatus[data.status];
  return (
    <div role="button" tabIndex={0} onClick={() => data.onSelect?.(data.nodeId)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") data.onSelect?.(data.nodeId); }} className="group relative w-[250px] select-none rounded-lg border border-[var(--border-1)] bg-[var(--surface-2)] text-[var(--text-primary)] shadow-[0_1px_2px_rgb(0_0_0/5%)]">
      <Handle type="target" position={Position.Top} id="target" className="!top-[-8px] !h-[7px] !w-5 !rounded-b-none !rounded-t-[2px] !border-0" style={{ background: statusColor }} />
      <div className="workflow-drag-handle flex h-11 cursor-grab items-center gap-2.5 border-b border-[var(--border-1)] p-2 active:cursor-grabbing">
        <span className="grid size-7 shrink-0 place-items-center rounded-md text-white" style={{ backgroundColor: statusColor }}>
          <Icon className="size-4" />
        </span>
        <span className="min-w-0 flex-1 truncate text-[14px] font-medium">{data.label}</span>
        <span className="flex shrink-0 items-center gap-1 text-[10px]" style={{ color: statusColor }}>
          {data.status === "running" && <Timer className="size-3 animate-spin" />}
          {data.status === "complete" && <Check className="size-3" />}
          {data.status === "error" && <X className="size-3" />}
          {labelByStatus[data.status]}
        </span>
      </div>
      <div className="min-h-[52px] p-2 text-[11px] leading-5 text-[var(--text-muted)]">
        <p className="line-clamp-2">{data.detail}</p>
      </div>
      <Handle type="source" position={Position.Bottom} id="source" className="!bottom-[-8px] !h-[7px] !w-5 !rounded-b-[2px] !rounded-t-none !border-0" style={{ background: statusColor }} />
    </div>
  );
});

const nodeTypes: NodeTypes = { workflowBlock: WorkflowBlock };

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
  const nodes: Node<WorkflowNodeData>[] = graph.nodes.map((node) => {
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
        <MiniMap nodeColor={(node) => colorByStatus[(node.data as WorkflowNodeData).status]} maskColor="rgb(248 248 248 / 0.7)" />
      </ReactFlow>
    </ReactFlowProvider>
  );
}
