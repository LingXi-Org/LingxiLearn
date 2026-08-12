"use client";

import { Activity, Boxes, CircleAlert, FileText, GitBranch, Sparkles } from "lucide-react";
import { useState } from "react";
import { SimButton } from "@/components/sim/source/button";
import { SimAgentGraph } from "@/components/sim/sim-agent-graph";
import type { SimMockRun } from "@/lib/sim-mock";

type ResourceTab = "graph" | "resources" | "capabilities" | "log";

export function SimResourcePanel({ run, onBackToConversation }: { run: SimMockRun; onBackToConversation?: () => void }) {
  const [tab, setTab] = useState<ResourceTab>("graph");
  return (
    <section className="flex h-full min-h-0 flex-col bg-[var(--surface-2)]" data-testid="sim-resource-panel">
      <header className="flex min-h-10 shrink-0 items-center gap-2 overflow-x-auto border-b border-[var(--border)] bg-[var(--surface-1)] px-3">
        <span className="grid size-6 shrink-0 place-items-center rounded-md bg-[var(--surface-4)] text-[var(--text-icon)]"><GitBranch className="size-3.5" /></span>
        <span className="shrink-0 text-xs font-medium">Resources</span>
        <nav className="ml-2 flex h-10 items-center gap-1" aria-label="Sim resources">
          <ResourceTab active={tab === "graph"} onClick={() => setTab("graph")} icon={<GitBranch className="size-3" />}>Graph</ResourceTab>
          <ResourceTab active={tab === "resources"} onClick={() => setTab("resources")} icon={<Boxes className="size-3" />}>Artifacts</ResourceTab>
          <ResourceTab active={tab === "capabilities"} onClick={() => setTab("capabilities")} icon={<Sparkles className="size-3" />}>Sim native</ResourceTab>
          <ResourceTab active={tab === "log"} onClick={() => setTab("log")} icon={<Activity className="size-3" />}>Run log</ResourceTab>
        </nav>
        {onBackToConversation && <SimButton type="button" variant="quiet" size="sm" className="ml-auto shrink-0 lg:hidden" onClick={onBackToConversation}>Back to chat</SimButton>}
      </header>
      <div className="min-h-0 flex-1 overflow-auto p-4 sm:p-5">
        {tab === "graph" && <SimAgentGraph graph={run.graph} />}
        {tab === "resources" && <ResourceList run={run} />}
        {tab === "capabilities" && <CapabilityList run={run} />}
        {tab === "log" && <RunLog run={run} />}
      </div>
    </section>
  );
}

function ResourceList({ run }: { run: SimMockRun }) {
  return <div className="mx-auto max-w-2xl"><PanelHeading icon={<Boxes className="size-4" />} title="Sim resource placeholders" detail="LingxiGraph learning artifacts are intentionally not called in this demo." /><div className="mt-4 space-y-2">{run.resources.map((resource) => <div key={resource.id} className="flex items-center gap-3 rounded-xl border border-dashed border-[var(--border)] bg-[var(--surface-1)] px-3 py-3"><span className="grid size-8 shrink-0 place-items-center rounded-lg bg-[var(--surface-4)] text-[var(--text-icon)]">{resource.kind === "background" ? <FileText className="size-4" /> : resource.kind === "visual" ? <Sparkles className="size-4" /> : <Boxes className="size-4" />}</span><span className="min-w-0 flex-1"><span className="block text-xs font-medium">{resource.title}</span><span className="mt-0.5 block text-[11px] text-[var(--text-muted)]">{resource.description}</span></span><SimButton type="button" variant="quiet" size="sm" disabled>{resource.available ? "Open" : "Placeholder"}</SimButton></div>)}</div></div>;
}

function CapabilityList({ run }: { run: SimMockRun }) {
  const categories = ["conversation", "agent", "workspace", "platform"] as const;
  return <div className="mx-auto max-w-3xl"><PanelHeading icon={<Sparkles className="size-4" />} title="Sim native capabilities" detail="所有未对接 LingxiGraph 的 Sim 能力在这里以明确占位展示。" /><div className="mt-4 grid gap-2 sm:grid-cols-2">{categories.flatMap((category) => run.capabilities.filter((capability) => capability.category === category)).map((capability) => <div key={capability.id} className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--surface-1)] p-3"><div className="flex items-center gap-2"><span className="size-1.5 rounded-full bg-[var(--text-muted)]" /><span className="text-xs font-medium">{capability.title}</span><span className="ml-auto rounded bg-[var(--surface-3)] px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-[var(--text-muted)]">placeholder</span></div><p className="mt-2 text-[11px] leading-5 text-[var(--text-muted)]">{capability.description}</p></div>)}</div></div>;
}

function RunLog({ run }: { run: SimMockRun }) {
  return <div className="mx-auto max-w-2xl"><PanelHeading icon={<Activity className="size-4" />} title="Run log" detail="Deterministic local event stream · no SSE connection" /><div className="mt-4 space-y-2">{run.log.map((entry, index) => <div key={`${entry}-${index}`} className="flex items-center gap-3 rounded-lg border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2 text-xs"><span className="font-mono text-[var(--text-muted)]">{String(index + 1).padStart(3, "0")}</span><span className="min-w-0 flex-1">{entry}</span><span className="text-[10px] text-[var(--brand)]">mock</span></div>)}</div><div className="mt-4 flex items-start gap-2 rounded-lg border border-dashed border-[var(--border)] bg-[var(--surface-3)] p-3 text-[11px] leading-5 text-[var(--text-muted)]"><CircleAlert className="mt-0.5 size-3.5 shrink-0" />所有日志均为前端占位事件，不代表 LingxiGraph 已执行。</div></div>;
}

function PanelHeading({ icon, title, detail }: { icon: React.ReactNode; title: string; detail: string }) {
  return <div className="flex items-start gap-2"><span className="grid size-7 place-items-center rounded-lg bg-[var(--surface-4)] text-[var(--text-icon)]">{icon}</span><div><h2 className="text-sm font-medium">{title}</h2><p className="mt-1 text-[11px] leading-5 text-[var(--text-muted)]">{detail}</p></div></div>;
}

function ResourceTab({ active, onClick, icon, children }: { active: boolean; onClick: () => void; icon: React.ReactNode; children: React.ReactNode }) {
  return <button type="button" onClick={onClick} className={`flex h-full shrink-0 items-center gap-1.5 border-b-2 px-2 text-[11px] transition-colors ${active ? "border-[var(--brand)] text-[var(--text-primary)]" : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]"}`}>{icon}{children}</button>;
}
