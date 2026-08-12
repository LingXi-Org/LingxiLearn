"use client";

import { memo, type ComponentType } from "react";
import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import { Bot, Check, GitBranch, Merge, Play, Sparkles, Timer, X } from "lucide-react";
import type { AgentCanvasNodeKind, AgentCanvasStatus } from "@/lib/sim-adapter";

export type SimWorkflowBlockData = {
  label: string;
  kind: AgentCanvasNodeKind;
  status: AgentCanvasStatus;
  detail: string;
  nodeId: string;
  onSelect?: (id: string) => void;
};

const iconByKind: Record<AgentCanvasNodeKind, ComponentType<{ className?: string }>> = { input: Play, intent: Sparkles, agent: Bot, merge: Merge };
const colorByStatus: Record<AgentCanvasStatus, string> = { pending: "#a3a3a3", running: "#7f77dd", complete: "#1d9e75", error: "#d85a30" };
const labelByStatus: Record<AgentCanvasStatus, string> = { pending: "等待", running: "执行中", complete: "完成", error: "失败" };

/** Read-only host binding for Sim's current WorkflowBlockView renderer. */
export const SimWorkflowBlock = memo(function SimWorkflowBlock({ data }: NodeProps<Node<SimWorkflowBlockData>>) {
  const Icon = iconByKind[data.kind] ?? GitBranch;
  const statusColor = colorByStatus[data.status];
  return (
    <div role="button" tabIndex={0} onClick={() => data.onSelect?.(data.nodeId)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") data.onSelect?.(data.nodeId); }} className="group relative w-[250px] select-none rounded-lg border border-[var(--border-1)] bg-[var(--surface-2)] text-[var(--text-primary)] shadow-[0_1px_2px_rgb(0_0_0/5%)]">
      <Handle type="target" position={Position.Top} id="target" className="!top-[-8px] !h-[7px] !w-5 !rounded-b-none !rounded-t-[2px] !border-0" style={{ background: statusColor }} />
      <div className="workflow-drag-handle flex h-11 cursor-grab items-center gap-2.5 border-b border-[var(--border-1)] p-2 active:cursor-grabbing">
        <span className="grid size-7 shrink-0 place-items-center rounded-md text-white" style={{ backgroundColor: statusColor }}><Icon className="size-4" /></span>
        <span className="min-w-0 flex-1 truncate text-[14px] font-medium">{data.label}</span>
        <span className="flex shrink-0 items-center gap-1 text-[10px]" style={{ color: statusColor }}>{data.status === "running" && <Timer className="size-3 animate-spin" />}{data.status === "complete" && <Check className="size-3" />}{data.status === "error" && <X className="size-3" />}{labelByStatus[data.status]}</span>
      </div>
      <div className="min-h-[52px] p-2 text-[11px] leading-5 text-[var(--text-muted)]"><p className="line-clamp-2">{data.detail}</p></div>
      <Handle type="source" position={Position.Bottom} id="source" className="!bottom-[-8px] !h-[7px] !w-5 !rounded-b-[2px] !rounded-t-none !border-0" style={{ background: statusColor }} />
    </div>
  );
});

export { colorByStatus };
