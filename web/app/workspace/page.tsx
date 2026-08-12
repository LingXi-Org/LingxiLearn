"use client";

import { Suspense, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Group, Panel, Separator, useGroupRef, type Layout } from "react-resizable-panels";
import { MessagesSquare } from "lucide-react";
import { SimAppShell } from "@/components/sim/sim-app-shell";
import { SimChat } from "@/components/sim/sim-chat";
import { SimResourcePanel, type ResourceTab } from "@/components/sim/sim-resource-panel";
import { SimButton } from "@/components/sim/source/button";
import { ApiError, api } from "@/lib/api";
import { useAgentTask } from "@/hooks/use-agent-task";
import { agentTaskToSimActivity, agentTaskToSimMessages, draftToSimMessages } from "@/lib/sim-adapter";
import { useOidcAdapter } from "@/components/auth/oidc-adapter";

const LAYOUT_KEY = "lingxilearn.workspace.layout";

export default function WorkspacePage() {
  return <Suspense fallback={<WorkspaceLoading />}><Workspace /></Suspense>;
}

function Workspace() {
  const params = useSearchParams();
  const router = useRouter();
  const taskId = params.get("task") || "";
  const prompt = params.get("prompt")?.trim() || "";
  const requestedTab = parseResourceTab(params.get("panel"));
  const { task, events, error: taskError, loading } = useAgentTask(taskId);
  const { configured: oidcConfigured, isAuthenticated, isLoading: authLoading, signIn } = useOidcAdapter();
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string>();
  const [mobileView, setMobileView] = useState<"conversation" | "artifact">("conversation");
  const [isDesktop, setIsDesktop] = useState(false);
  const [layoutReady, setLayoutReady] = useState(false);
  const groupRef = useGroupRef();
  const bootstrappedPrompt = useRef<string | undefined>(undefined);

  useEffect(() => {
    if (taskId || !prompt || bootstrappedPrompt.current === prompt) return;
    if (oidcConfigured && authLoading) return;
    if (oidcConfigured && !isAuthenticated) {
      setCreateError("请先登录后再创建 Agent 任务。");
      return;
    }
    bootstrappedPrompt.current = prompt;
    setCreating(true);
    setCreateError(undefined);
    void api.createAgentTask(prompt)
      .then((created) => router.replace(`/workspace/?task=${encodeURIComponent(created.id)}`))
      .catch((cause) => setCreateError(cause instanceof Error ? cause.message : String(cause)))
      .finally(() => setCreating(false));
  }, [authLoading, isAuthenticated, oidcConfigured, prompt, router, taskId]);

  useEffect(() => setLayoutReady(true), []);

  useLayoutEffect(() => {
    const media = window.matchMedia("(min-width: 1024px)");
    const update = () => setIsDesktop(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  useLayoutEffect(() => {
    try {
      const stored = window.localStorage.getItem(LAYOUT_KEY);
      if (stored && isDesktop) groupRef.current?.setLayout(JSON.parse(stored) as Layout);
    } catch {
      /* Invalid preferences fall back to the default layout. */
    }
  }, [groupRef, isDesktop]);

  const saveLayout = useCallback((layout: Layout) => window.localStorage.setItem(LAYOUT_KEY, JSON.stringify(layout)), []);
  const handleSend = useCallback(async (text: string) => {
    setCreating(true);
    setCreateError(undefined);
    try {
      if (taskId) {
        await api.agentMessage(taskId, text);
      } else {
        const created = await api.createAgentTask(text);
        router.push(`/workspace/?task=${encodeURIComponent(created.id)}`);
      }
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) {
        setCreateError("登录状态无效或已过期，请重新登录后再试。");
      } else {
        setCreateError(cause instanceof Error ? cause.message : String(cause));
      }
    } finally {
      setCreating(false);
    }
  }, [router, taskId]);

  const messages = task ? agentTaskToSimMessages(task, events) : prompt ? draftToSimMessages(prompt) : [];
  const activity = agentTaskToSimActivity(task, events);
  const error = createError || taskError;
  const title = task?.intent.topic || task?.prompt || prompt || "新问题";
  const conversation = <SimChat messages={messages} activity={activity} placeholder={task?.status === "awaiting_user" ? "继续追问，或说明是否要答题…" : "输入你想学习的问题…"} disabled={loading && !task || creating || (oidcConfigured && !isAuthenticated)} running={creating || Boolean(task && (task.status === "queued" || task.status === "running"))} onSend={handleSend} header={<header className="flex h-11 shrink-0 items-center gap-2 border-b border-[var(--border)] bg-[var(--surface-1)] px-4"><span className="size-1.5 rounded-full bg-[var(--brand)]" /><span className="min-w-0 flex-1 truncate text-[12px] font-medium">{title}</span><span className="text-[10px] text-[var(--text-muted)]">{task ? statusLabel(task.status) : creating ? "正在创建" : "待开始"}</span><SimButton type="button" variant="quiet" size="sm" className="lg:hidden" onClick={() => setMobileView("artifact")}>工作区</SimButton></header>} notice={error || (oidcConfigured && !isAuthenticated && !authLoading) ? <div className="mb-2 flex items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[11px] text-red-800"><span>{error || "请先登录后再创建 Agent 任务。"}</span><SimButton type="button" variant="quiet" size="sm" onClick={() => void signIn()}>登录</SimButton></div> : undefined} />;
  const viewer = <SimResourcePanel task={task} events={events} initialTab={requestedTab} onBackToConversation={() => setMobileView("conversation")} />;
  const content = <div className={layoutReady ? "sim-three-column-layout sim-layout-ready h-full min-h-0 bg-[var(--bg)]" : "sim-three-column-layout sim-layout-entering h-full min-h-0 bg-[var(--bg)]"}>{isDesktop ? <Group groupRef={groupRef} orientation="horizontal" defaultLayout={{ conversation: 38, artifact: 62 }} onLayoutChanged={saveLayout}><Panel id="conversation" minSize="28%" maxSize="58%"><div className="sim-conversation-pane h-full min-h-0">{conversation}</div></Panel><Separator id="workspace-separator" aria-label="调整对话与工作区宽度" title="拖动调整宽度，双击恢复默认" onDoubleClick={() => groupRef.current?.setLayout({ conversation: 38, artifact: 62 })} className="workspace-resize-handle group relative z-20 w-2 shrink-0 cursor-col-resize touch-none bg-[var(--bg)] outline-none"><span className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-[var(--border)] transition-all group-hover:w-0.5 group-hover:bg-[var(--text-primary)] group-focus-visible:w-0.5" /></Separator><Panel id="artifact" minSize="42%"><div className="sim-artifact-pane h-full min-h-0">{viewer}</div></Panel></Group> : <div className="h-full lg:hidden"><div className={mobileView === "conversation" ? "h-full" : "hidden"}>{conversation}</div><div className={mobileView === "artifact" ? "h-full" : "hidden"}>{viewer}</div></div>}</div>;
  return <SimAppShell title={title} currentTaskId={task?.id || taskId || undefined} taskStatus={task?.status}><>{content}</></SimAppShell>;
}

function parseResourceTab(value: string | null): ResourceTab {
  return value === "lecture-deck" || value === "quiz" || value === "visual" ? value : "canvas";
}

function statusLabel(status?: string) {
  return status === "handed_off" ? "已返回主图" : status === "awaiting_user" ? "等待你的输入" : status === "completed" ? "已完成" : status === "partial" ? "部分完成" : status === "failed" ? "失败" : status === "running" ? "执行中" : "排队中";
}

function WorkspaceLoading() {
  return <div className="grid h-dvh place-items-center bg-[var(--bg)]"><div className="flex items-center gap-2 text-xs text-[var(--text-muted)]"><MessagesSquare className="size-4 animate-pulse" /> 正在打开 Agent 工作台…</div></div>;
}
