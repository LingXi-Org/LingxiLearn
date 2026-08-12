"use client";

import { GitBranch } from "lucide-react";
import { useEffect, useState } from "react";
import { SimButton } from "@/components/sim/source/button";
import { SimResourceTab } from "@/components/sim/source/resource-tab";
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
  const hasLecture = Boolean(task?.artifacts.background.available);
  const hasVisual = Boolean(task?.artifacts.visual.available);

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
          <SimResourceTab active={tab === "canvas"} onClick={() => setTab("canvas")} icon={<GitBranch className="size-3" />}>Canvas</SimResourceTab>
          {hasLecture && <SimResourceTab active={tab === "background"} onClick={() => setTab("background")}>课程引入设计</SimResourceTab>}
          {hasVisual && <SimResourceTab active={tab === "visual"} onClick={() => setTab("visual")}>交互式可视化讲解</SimResourceTab>}
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
  return artifact.content ? <iframe title="课程引入设计" src={artifact.content} sandbox="allow-scripts" className="h-full min-h-[520px] w-full border-0 bg-white" /> : null;
}

function VisualArtifact({ task }: { task: AgentTaskSnapshot | null }) {
  const available = Boolean(task?.artifacts.visual.available);
  const artifact = useAgentArtifact(task?.id, "visual", available);
  return artifact.content ? <iframe title="交互式可视化讲解" src={artifact.content} sandbox="allow-scripts" className="h-full min-h-[520px] w-full border-0 bg-white" /> : null;
}
