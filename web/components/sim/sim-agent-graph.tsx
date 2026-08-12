"use client";

import { GitBranch } from "lucide-react";
import { useState } from "react";
import { SimAgentGroup } from "@/components/sim/source/agent-group";
import { SimWorkflowCanvas } from "@/components/sim/source/workflow-canvas";
import type { AgentCanvasGraph, SimAgentRun } from "@/lib/sim-adapter";

export function SimAgentGraph({ graph, runs, running }: { graph: AgentCanvasGraph; runs: SimAgentRun[]; running: boolean }) {
  const [selectedAgent, setSelectedAgent] = useState<string>();
  const selected = runs.find((run) => run.agent === selectedAgent);
  return (
    <div className="flex h-full min-h-[520px] flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface-1)]" data-testid="sim-agent-graph">
      <div className="flex shrink-0 items-center gap-2 border-b border-[var(--border)] px-4 py-3">
        <GitBranch className="size-4 text-[var(--brand)]" />
        <div>
          <h3 className="text-sm font-medium">Agent orchestration</h3>
          <p className="text-[11px] text-[var(--text-muted)]">LingxiGraph 实时任务编排</p>
        </div>
      </div>
      <div className="min-h-0 flex-1">
        <SimWorkflowCanvas graph={graph} onNodeSelect={setSelectedAgent} />
      </div>
      {selected && <div className="shrink-0 border-t border-[var(--border)] bg-[var(--surface-1)] p-3"><SimAgentGroup key={selected.agent} run={selected} isStreaming={running} defaultExpanded /></div>}
    </div>
  );
}
