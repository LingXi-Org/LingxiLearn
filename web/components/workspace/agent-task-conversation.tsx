"use client";

import { Check, CircleAlert, LoaderCircle, Menu, PanelLeft, Sparkles } from "lucide-react";
import type { AgentTaskEvent, AgentTaskSnapshot } from "@/lib/types";

const AGENTS = [
  { key: "intent", label: "意图识别", description: "提炼知识点和学习目标" },
  { key: "lecture_hook", label: "背景文档 Agent", description: "研究背景并建立证据账本" },
  { key: "visual_explainer", label: "可视化 Agent", description: "生成可交互的离线讲解页" },
] as const;

export function AgentTaskConversation({
  task,
  events,
  onMenu,
  onArtifact,
}: {
  task: AgentTaskSnapshot | null;
  events: AgentTaskEvent[];
  onMenu?: () => void;
  onArtifact?: () => void;
}) {
  const status = task?.status ?? "queued";
  return (
    <div className="flex h-full min-h-0 flex-col bg-[#fafafa]">
      <header className="flex h-[52px] shrink-0 items-center gap-2 border-b border-[#dedede] bg-[#fafafa] px-3">
        <img src="/logo_icon.svg" alt="" className="size-7" />
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-[15px] font-medium">意图调度工作台</h1>
        </div>
        {onMenu && <button onClick={onMenu} className="grid size-8 place-items-center rounded-full hover:bg-black/[.05] lg:hidden" aria-label="打开任务列表"><Menu className="size-4" /></button>}
        {onArtifact && <button onClick={onArtifact} className="grid size-8 place-items-center rounded-lg bg-[var(--surface-2)] lg:hidden" aria-label="打开工作区"><PanelLeft className="size-4" /></button>}
        <span className="rounded-full bg-[#eeeefc] px-2.5 py-1 text-[10px] font-medium text-[#5047a8]">
          {statusLabel(status)}
        </span>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 pt-7">
        <div className="mx-auto w-full max-w-[760px]">
          {task?.prompt && (
            <div className="ml-auto max-w-[88%] rounded-2xl bg-[#ececec] px-4 py-2.5 text-[15px] leading-6">
              {task.prompt}
            </div>
          )}
          <div className="mt-8 border-l border-[#cfcfcf] pl-4">
            <div className="flex items-center gap-2 text-sm font-medium text-[#202020]">
              <Sparkles className="size-4 text-[#5b5ce2]" />
              Agent 正在并行准备两份学习产物
            </div>
            <div className="mt-4 space-y-3">
              {AGENTS.map((agent) => {
                const agentState = task?.agents[agent.key];
                const failed = agentState?.status === "failed";
                const completed = agentState?.status === "completed";
                const live = events.some((event) => event.agent === agent.key && event.kind.endsWith("started"));
                return (
                  <div key={agent.key} className="flex items-start gap-3 rounded-xl border border-[#dedede] bg-white px-3 py-3">
                    <span className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-full ${failed ? "bg-red-50 text-red-600" : completed ? "bg-emerald-50 text-emerald-600" : "bg-[#f0efff] text-[#5b5ce2]"}`}>
                      {failed ? <CircleAlert className="size-3.5" /> : completed ? <Check className="size-3.5" /> : <LoaderCircle className={`size-3.5 ${live || status === "running" ? "animate-spin" : ""}`} />}
                    </span>
                    <div className="min-w-0">
                      <div className="text-xs font-medium text-[#202020]">{agent.label}</div>
                      <div className="mt-0.5 text-[11px] leading-5 text-[#777]">
                        {failed ? agentState?.error || "执行失败，右侧会保留可用产物。" : completed ? "已完成，产物已同步到右侧工作区。" : agent.description}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
            {task?.intent.topic && (
              <div className="mt-4 rounded-lg bg-[#f3f3f3] px-3 py-2 text-xs leading-5 text-[#666]">
                当前知识点：<span className="font-medium text-[#222]">{task.intent.topic}</span>
              </div>
            )}
            {task?.error && <p className="mt-4 text-xs leading-5 text-red-600">{task.error}</p>}
          </div>
        </div>
      </div>
      <div className="shrink-0 border-t border-[#dedede] bg-[#fafafa] px-4 py-3 text-center text-xs text-[#999]">
        本次任务完成后，可在右侧切换查看背景文档和可视化讲解。
      </div>
    </div>
  );
}

function statusLabel(status: AgentTaskSnapshot["status"] | "queued") {
  if (status === "completed") return "已完成";
  if (status === "partial") return "部分完成";
  if (status === "failed") return "执行失败";
  if (status === "running") return "执行中";
  return "排队中";
}
