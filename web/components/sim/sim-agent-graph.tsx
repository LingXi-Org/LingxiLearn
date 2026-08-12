"use client";

import { Bot, Boxes, Check, GitBranch, Wrench } from "lucide-react";
import type { SimMockGraphNode } from "@/lib/sim-mock";

export function SimAgentGraph({ graph }: { graph: { nodes: SimMockGraphNode[]; edges: { from: string; to: string; label: string }[] } }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-1)] p-4" data-testid="sim-agent-graph">
      <div className="mb-3 flex items-center gap-2">
        <GitBranch className="size-4 text-[var(--brand)]" />
        <div>
          <h3 className="text-sm font-medium">Agent orchestration</h3>
          <p className="text-[11px] text-[var(--text-muted)]">Sim 原生编排图占位 · local mock only</p>
        </div>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {graph.nodes.map((node) => <GraphNode key={node.id} node={node} />)}
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5 border-t border-[var(--border)] pt-3">
        {graph.edges.map((edge) => <span key={`${edge.from}-${edge.to}`} className="rounded-md bg-[var(--surface-3)] px-2 py-1 text-[10px] text-[var(--text-muted)]">{edge.from} <span className="text-[var(--brand)]">→</span> {edge.to} · {edge.label}</span>)}
      </div>
    </div>
  );
}

function GraphNode({ node }: { node: SimMockGraphNode }) {
  const Icon = node.kind === "tool" ? Wrench : node.kind === "resource" ? Boxes : node.kind === "agent" ? Bot : GitBranch;
  return <div className="flex min-w-0 items-center gap-2 rounded-lg border border-dashed border-[var(--border)] bg-[var(--surface-2)] px-3 py-2"><span className="grid size-7 shrink-0 place-items-center rounded-md bg-[var(--surface-4)] text-[var(--text-icon)]"><Icon className="size-3.5" /></span><span className="min-w-0 flex-1"><span className="block truncate text-xs font-medium">{node.label}</span><span className="block truncate text-[10px] text-[var(--text-muted)]">{node.detail}</span></span><span className="flex shrink-0 items-center gap-1 text-[10px] text-[var(--brand)]"><Check className="size-3" />{node.status}</span></div>;
}
