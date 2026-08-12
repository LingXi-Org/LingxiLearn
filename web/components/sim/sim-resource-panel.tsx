"use client";

import { AlertCircle, Bot, FileText, GitBranch, LoaderCircle, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { SimButton } from "@/components/sim/source/button";
import { SimAgentGraph } from "@/components/sim/sim-agent-graph";
import { useAgentArtifact } from "@/hooks/use-agent-artifact";
import { agentTaskToAgentRuns, agentTaskToCanvasGraph } from "@/lib/sim-adapter";
import type { AgentTaskEvent, AgentTaskSnapshot } from "@/lib/types";

export type ResourceTab = "canvas" | "background" | "visual";

export function SimResourcePanel({
  task,
  events,
  initialTab = "canvas",
  onBackToConversation,
}: {
  task: AgentTaskSnapshot | null;
  events: AgentTaskEvent[];
  initialTab?: ResourceTab;
  onBackToConversation?: () => void;
}) {
  const [tab, setTab] = useState<ResourceTab>(initialTab);
  useEffect(() => setTab(initialTab), [initialTab]);
  const graph = agentTaskToCanvasGraph(task, events);
  const runs = task ? agentTaskToAgentRuns(task, events) : [];
  const hasLecture = events.some((event) => event.agent === "lecture_hook") || Boolean(task?.artifacts.background.available);
  const hasVisual = events.some((event) => event.agent === "visual_explainer") || Boolean(task?.artifacts.visual.available);

  useEffect(() => {
    if (tab === "background" && !hasLecture) setTab("canvas");
    if (tab === "visual" && !hasVisual) setTab("canvas");
  }, [hasLecture, hasVisual, tab]);

  if (!task) {
    return <section className="flex h-full min-h-0 items-center justify-center bg-[var(--surface-2)]" data-testid="sim-resource-panel"><div className="text-center text-xs text-[var(--text-muted)]"><GitBranch className="mx-auto mb-3 size-5 opacity-40" /><p>工作区将在提交问题后动态加载</p></div></section>;
  }

  return (
    <section className="flex h-full min-h-0 flex-col bg-[var(--surface-2)]" data-testid="sim-resource-panel">
      <header className="flex min-h-10 shrink-0 items-center gap-2 overflow-x-auto border-b border-[var(--border)] bg-[var(--surface-1)] px-3">
        <span className="grid size-6 shrink-0 place-items-center rounded-md bg-[var(--surface-4)] text-[var(--text-icon)]"><GitBranch className="size-3.5" /></span>
        <span className="shrink-0 text-xs font-medium">工作区</span>
        <nav className="ml-2 flex h-10 items-center gap-1" aria-label="Agent 工作区页面">
          <ResourceTab active={tab === "canvas"} onClick={() => setTab("canvas")} icon={<GitBranch className="size-3" />}>Canvas</ResourceTab>
          {hasLecture && <ResourceTab active={tab === "background"} onClick={() => setTab("background")} icon={<FileText className="size-3" />}>Lecture hook</ResourceTab>}
          {hasVisual && <ResourceTab active={tab === "visual"} onClick={() => setTab("visual")} icon={<Sparkles className="size-3" />}>Visual explainer</ResourceTab>}
        </nav>
        {onBackToConversation && <SimButton type="button" variant="quiet" size="sm" className="ml-auto shrink-0 lg:hidden" onClick={onBackToConversation}>返回对话</SimButton>}
      </header>
      <div className="min-h-0 flex-1 overflow-auto p-4 sm:p-5">
        {tab === "canvas" && <SimAgentGraph graph={graph} runs={runs} running={task.status === "queued" || task.status === "running"} />}
        {tab === "background" && <BackgroundArtifact task={task} />}
        {tab === "visual" && <VisualArtifact task={task} />}
      </div>
    </section>
  );
}

function BackgroundArtifact({ task }: { task: AgentTaskSnapshot | null }) {
  const available = Boolean(task?.artifacts.background.available);
  const artifact = useAgentArtifact(task?.id, "background", available);
  return (
    <ArtifactFrame icon={<FileText className="size-4" />} title="Lecture hook 背景产物" agent="lecture_hook" available={available} loading={artifact.loading} error={artifact.error}>
      {artifact.content && <article className="prose prose-sm max-w-none whitespace-pre-wrap text-[13px] leading-7 text-[var(--text-primary)]">{artifact.content}</article>}
    </ArtifactFrame>
  );
}

function VisualArtifact({ task }: { task: AgentTaskSnapshot | null }) {
  const available = Boolean(task?.artifacts.visual.available);
  const artifact = useAgentArtifact(task?.id, "visual", available);
  return (
    <ArtifactFrame icon={<Sparkles className="size-4" />} title="Visual explainer 交互页面" agent="visual_explainer" available={available} loading={artifact.loading} error={artifact.error}>
      {artifact.content && <iframe title="Visual explainer artifact" src={artifact.content} sandbox="allow-scripts" className="h-[min(72vh,760px)] w-full rounded-lg border border-[var(--border)] bg-white" />}
    </ArtifactFrame>
  );
}

function ArtifactFrame({ icon, title, agent, available, loading, error, children }: { icon: React.ReactNode; title: string; agent: string; available: boolean; loading: boolean; error?: string; children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-4 flex items-start gap-3">
        <span className="grid size-8 place-items-center rounded-lg bg-[var(--surface-4)] text-[var(--text-icon)]">{icon}</span>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-medium">{title}</h2>
          <p className="mt-1 text-[11px] text-[var(--text-muted)]">由 {agent} Agent 生成，内容来自当前任务 Artifact。</p>
        </div>
        <span className="flex shrink-0 items-center gap-1 text-[11px] text-[var(--text-muted)]">
          {loading && <LoaderCircle className="size-3 animate-spin" />}
          {available ? "已就绪" : "等待产物"}
        </span>
      </div>
      {!available && <EmptyArtifact agent={agent} />}
      {available && loading && <div className="grid min-h-40 place-items-center rounded-xl border border-[var(--border)] bg-[var(--surface-1)] text-xs text-[var(--text-muted)]"><LoaderCircle className="mr-2 inline size-4 animate-spin" />正在读取 Artifact…</div>}
      {available && error && <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-xs leading-5 text-red-800"><AlertCircle className="mt-0.5 size-4 shrink-0" />Artifact 加载失败：{error}</div>}
      {available && !loading && !error && children}
    </div>
  );
}

function EmptyArtifact({ agent }: { agent: string }) {
  return <div className="grid min-h-64 place-items-center rounded-xl border border-dashed border-[var(--border)] bg-[var(--surface-1)] px-6 text-center text-xs text-[var(--text-muted)]"><div><Bot className="mx-auto size-5 text-[var(--text-icon)]" /><p className="mt-3">{agent} 尚未生成产物。</p><p className="mt-1">任务运行完成后，这里会自动显示真实内容。</p></div></div>;
}

function ResourceTab({ active, onClick, icon, children }: { active: boolean; onClick: () => void; icon: React.ReactNode; children: React.ReactNode }) {
  return <button type="button" onClick={onClick} className={`flex h-full shrink-0 items-center gap-1.5 border-b-2 px-2 text-[11px] transition-colors ${active ? "border-[var(--brand)] text-[var(--text-primary)]" : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]"}`}>{icon}{children}</button>;
}
