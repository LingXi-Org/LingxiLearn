"use client";

import { useEffect, useState } from "react";
import { ArrowLeft, Check, CircleAlert, ExternalLink, FileText, RefreshCw, Sparkles } from "lucide-react";
import { Streamdown } from "streamdown";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { AgentTaskEvent, AgentTaskSnapshot } from "@/lib/types";

export function AgentTaskWorkspace({
  task,
  events,
  onBackToConversation,
}: {
  task: AgentTaskSnapshot | null;
  events: AgentTaskEvent[];
  onBackToConversation?: () => void;
}) {
  const [tab, setTab] = useState<"background" | "visual">("background");
  return (
    <section className="flex h-full min-h-0 flex-col bg-white" data-testid="agent-task-workspace">
      <header className="flex h-[52px] shrink-0 items-center gap-3 border-b border-[#dedede] bg-white px-3 sm:px-4">
        {onBackToConversation && <button onClick={onBackToConversation} className="grid size-8 place-items-center rounded-lg hover:bg-[#f5f5f5] lg:hidden" aria-label="返回对话"><ArrowLeft className="size-4" /></button>}
        <span className="grid size-8 place-items-center rounded-full border border-black/[.09] bg-white text-[var(--muted)]"><Sparkles className="size-4" /></span>
        <div className="min-w-0 flex-1"><h2 className="truncate text-sm font-medium">Agent 学习产物</h2><p className="truncate text-[10px] text-[#999]">{task?.intent.topic || "正在读取意图…"}</p></div>
        <Button variant="outline" size="icon" onClick={() => window.location.reload()} title="刷新"><RefreshCw className="size-4" /></Button>
      </header>
      <div className="flex shrink-0 gap-1 border-b border-[#dedede] bg-white px-3 pt-2">
        <TabButton active={tab === "background"} onClick={() => setTab("background")} icon={<FileText className="size-3.5" />}>背景文档</TabButton>
        <TabButton active={tab === "visual"} onClick={() => setTab("visual")} icon={<Sparkles className="size-3.5" />}>可视化讲解</TabButton>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden border border-[#dedede] bg-[#fafafa]">
        {tab === "background" ? <BackgroundDocument task={task} /> : <VisualArtifact task={task} events={events} />}
      </div>
    </section>
  );
}

function TabButton({ active, onClick, icon, children }: { active: boolean; onClick: () => void; icon: React.ReactNode; children: React.ReactNode }) {
  return <button type="button" onClick={onClick} className={`flex items-center gap-1.5 border-b-2 px-3 py-2 text-xs transition-colors ${active ? "border-[#5b5ce2] font-medium text-[#40389f]" : "border-transparent text-[#777] hover:text-[#222]"}`}>{icon}{children}</button>;
}

function BackgroundDocument({ task }: { task: AgentTaskSnapshot | null }) {
  const [content, setContent] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    if (!task?.artifacts.background.available) {
      setContent("");
      setError("");
      return;
    }
    let cancelled = false;
    setError("");
    api.fetchArtifact(api.agentArtifactUrl(task.id, "background"))
      .then((blob) => blob.text())
      .then((value) => { if (!cancelled) setContent(value); })
      .catch((cause: unknown) => { if (!cancelled) setError(cause instanceof Error ? cause.message : String(cause)); });
    return () => { cancelled = true; };
  }, [task?.id, task?.artifacts.background.available]);

  if (!task || !task.artifacts.background.available) return <ArtifactPending label="背景文档" detail="lecture-hook Agent 正在研究并核验来源。" failed={task?.agents.lecture_hook.status === "failed"} />;
  if (error) return <ArtifactError message={error} />;
  if (!content) return <ArtifactPending label="背景文档" detail="正在加载 Markdown 产物…" />;
  return <article className="h-full overflow-auto bg-[#fbfaf7] px-5 py-7 sm:px-10"><div className="mx-auto max-w-3xl text-[14px] leading-7 text-[#30302c]"><Streamdown>{content}</Streamdown></div></article>;
}

function VisualArtifact({ task, events }: { task: AgentTaskSnapshot | null; events: AgentTaskEvent[] }) {
  const [blobUrl, setBlobUrl] = useState<string>();
  const [error, setError] = useState<string>();
  useEffect(() => {
    if (!task || !task.artifacts.visual.available) {
      setBlobUrl(undefined);
      setError(undefined);
      return;
    }
    let cancelled = false;
    let objectUrl: string | undefined;
    setBlobUrl(undefined);
    setError(undefined);
    api.fetchArtifact(api.agentArtifactUrl(task.id, "visual"))
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setBlobUrl(objectUrl);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : String(cause));
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [task?.id, task?.artifacts.visual.available]);

  if (!task || !task.artifacts.visual.available) return <ArtifactPending label="可视化讲解" detail="visual-explainer Agent 正在生成并校验单文件 HTML。" failed={task?.agents.visual_explainer.status === "failed"} />;
  const metadata = task.artifacts.visual.metadata;
  const validation = metadata?.validation;
  if (error) return <ArtifactError message={error} />;
  return (
    <div className="flex h-full min-h-0 flex-col bg-[#f5f5f5]">
      <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-[#dedede] bg-white px-3 py-2 text-xs">
        <span className="font-medium">{metadata?.title || "可视化讲解"}</span>
        {validation?.ok ? <Badge variant="secondary"><Check className="size-3" />校验通过</Badge> : <Badge variant="outline"><CircleAlert className="size-3" />有校验提示</Badge>}
        <span className="ml-auto flex items-center gap-2"><a href={blobUrl || "#"} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[#5047a8] hover:underline">独立打开 <ExternalLink className="size-3" /></a><a href={blobUrl || "#"} download="visual-explainer.html" className="text-[#777] hover:text-[#222]">下载 HTML</a></span>
      </div>
      <iframe title={metadata?.title || "可视化讲解"} src={blobUrl} sandbox="allow-scripts" className="min-h-0 flex-1 border-0 bg-white" />
      {events.some((event) => event.kind === "agent.completed" && event.agent === "visual_explainer") && !validation?.ok && <div className="shrink-0 border-t border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-800">页面已生成，但静态检查仍有提示；不影响预览。</div>}
    </div>
  );
}

function ArtifactPending({ label, detail, failed = false }: { label: string; detail: string; failed?: boolean }) {
  return <div className="grid h-full place-items-center p-8 text-center"><div><span className={`mx-auto grid size-14 place-items-center rounded-2xl ${failed ? "bg-red-50 text-red-600" : "bg-white text-[#5b5ce2]"}`}>{failed ? <CircleAlert className="size-6" /> : <Sparkles className="size-6" />}</span><h3 className="mt-4 text-sm font-semibold">{failed ? `${label}生成失败` : label}</h3><p className="mx-auto mt-2 max-w-sm text-xs leading-5 text-[#777]">{failed ? "请查看左侧执行过程中的错误信息。" : detail}</p></div></div>;
}

function ArtifactError({ message }: { message: string }) {
  return <div className="grid h-full place-items-center p-8 text-center text-xs text-red-600"><CircleAlert className="mx-auto size-6" /><p className="mt-3">{message}</p></div>;
}
