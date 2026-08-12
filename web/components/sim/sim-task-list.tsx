"use client";

import { ListTodo } from "lucide-react";
import { SimAgentGroup } from "@/components/sim/source/agent-group";
import { agentTaskToAgentRuns, dedupeSimEvents, type AgentCanvasGraph } from "@/lib/sim-adapter";
import type { AgentTaskEvent, AgentTaskSnapshot } from "@/lib/types";

export function SimTaskList({ task, events, graph }: { task: AgentTaskSnapshot; events: AgentTaskEvent[]; graph: AgentCanvasGraph }) {
  const ordered = dedupeSimEvents(events);
  const runs = agentTaskToAgentRuns(task, ordered);
  return <div className="mx-auto flex max-w-5xl flex-col gap-4" data-testid="sim-task-list">
    <section className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface-1)]">
      <header className="flex items-center gap-2 border-b border-[var(--border)] px-4 py-3">
        <ListTodo className="size-4 text-[var(--brand)]" />
        <div className="min-w-0 flex-1"><h2 className="text-sm font-medium">任务列表</h2><p className="truncate text-[11px] text-[var(--text-muted)]">{task.id} · {task.prompt}</p></div>
        <span className="rounded-full bg-[var(--surface-4)] px-2 py-1 text-[10px] text-[var(--text-muted)]">{statusLabel(task.status)}</span>
      </header>
      <div className="grid gap-3 p-4 sm:grid-cols-3 text-xs text-[var(--text-muted)]"><span>Graph 节点：{graph.nodes.length}</span><span>执行事件：{ordered.length}</span><span>Agent：{runs.length}</span></div>
    </section>
    <section className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface-1)]">
      <div className="border-b border-[var(--border)] px-4 py-3"><h3 className="text-xs font-medium">Agent 思考与输出</h3><p className="mt-0.5 text-[11px] text-[var(--text-muted)]">使用 Sim 原生 AgentGroup 展示 skill 读取、思考、输出、工具调用、工具结果和中间产物。</p></div>
      <div className="divide-y divide-[var(--border)]">{runs.length === 0 ? <p className="p-4 text-xs text-[var(--text-muted)]">等待 Agent 事件…</p> : runs.map((run) => <div key={run.agent} className="p-4"><SimAgentGroup run={run} isStreaming={task.status === "queued" || task.status === "running"} defaultExpanded /></div>)}</div>
    </section>
  </div>;
}

function statusLabel(status: AgentTaskSnapshot["status"]) {
  return status === "running" ? "执行中" : status === "completed" ? "已完成" : status === "failed" ? "失败" : status === "awaiting_user" ? "等待输入" : status === "partial" ? "部分完成" : status === "handed_off" ? "已返回主图" : "排队中";
}
