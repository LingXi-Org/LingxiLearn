"use client";

import { Suspense, useCallback, useEffect, useLayoutEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Group, Panel, Separator, useGroupRef, type Layout } from "react-resizable-panels";
import { MessagesSquare } from "lucide-react";
import { consumeSimLayoutTransition, SimAppShell, markSimLayoutTransition } from "@/components/sim/sim-app-shell";
import { SimChat } from "@/components/sim/sim-chat";
import { SimResourcePanel } from "@/components/sim/sim-resource-panel";
import { SimButton } from "@/components/sim/source/button";
import { useSimMock } from "@/hooks/use-sim-mock";
import { mockSidebarData } from "@/lib/sim-mock";

const LAYOUT_KEY = "lingxilearn.workspace.layout";

export default function WorkspacePage() {
  return <Suspense fallback={<WorkspaceLoading />}><Workspace /></Suspense>;
}

function Workspace() {
  const params = useSearchParams();
  const router = useRouter();
  const sidebar = useMemo(() => mockSidebarData(), []);
  const initialPrompt = params.get("prompt") || (params.get("task") ? "Agent task placeholder" : params.get("id") ? "Learning session placeholder" : "New Sim conversation");
  const { run, send } = useSimMock(initialPrompt);
  const [mobileView, setMobileView] = useState<"conversation" | "artifact">("conversation");
  const [isDesktop, setIsDesktop] = useState(false);
  const [layoutReady, setLayoutReady] = useState(false);
  const groupRef = useGroupRef();

  useEffect(() => {
    const shouldAnimate = consumeSimLayoutTransition();
    if (!shouldAnimate) { setLayoutReady(true); return; }
    const frame = window.requestAnimationFrame(() => setLayoutReady(true));
    return () => window.cancelAnimationFrame(frame);
  }, []);

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
    } catch { /* invalid preferences fall back to the default layout */ }
  }, [groupRef, isDesktop]);

  const saveLayout = useCallback((layout: Layout) => window.localStorage.setItem(LAYOUT_KEY, JSON.stringify(layout)), []);
  const handleSend = useCallback((text: string) => send(text), [send]);
  const startMission = useCallback((missionId: string) => {
    const mission = sidebar.missionById.get(missionId);
    markSimLayoutTransition();
    router.push(`/workspace/?mock=1&prompt=${encodeURIComponent(mission?.title ?? "Sim workflow placeholder")}`);
  }, [router, sidebar.missionById]);
  const conversation = <SimChat messages={run.messages} activity={run.activity} placeholder="Ask the placeholder agent anything…" onSend={handleSend} header={<header className="flex h-11 shrink-0 items-center gap-2 border-b border-[var(--border)] bg-[var(--surface-1)] px-4"><span className="size-1.5 rounded-full bg-[var(--brand)]" /><span className="min-w-0 flex-1 truncate text-[12px] font-medium">{run.title}</span><span className="text-[10px] text-[var(--text-muted)]">local mock</span><SimButton type="button" variant="quiet" size="icon" className="lg:hidden" onClick={() => setMobileView("artifact")} aria-label="Open resources">Resources</SimButton></header>} notice={<div className="mb-2 rounded-lg border border-dashed border-[var(--border)] bg-[var(--surface-3)] px-3 py-2 text-[11px] text-[var(--text-muted)]">占位模式：不调用真实 REST、SSE、身份认证或 LingxiGraph API。</div>} />;
  const viewer = <SimResourcePanel run={run} onBackToConversation={() => setMobileView("conversation")} />;
  const content = <div className={layoutReady ? "sim-three-column-layout sim-layout-ready h-full min-h-0 bg-[var(--bg)]" : "sim-three-column-layout sim-layout-entering h-full min-h-0 bg-[var(--bg)]"}>{isDesktop ? <Group groupRef={groupRef} orientation="horizontal" defaultLayout={{ conversation: 38, artifact: 62 }} onLayoutChanged={saveLayout}><Panel id="conversation" minSize="28%" maxSize="58%"><div className="sim-conversation-pane h-full min-h-0">{conversation}</div></Panel><Separator id="workspace-separator" aria-label="调整对话与工作区宽度" title="拖动调整宽度，双击恢复默认" onDoubleClick={() => groupRef.current?.setLayout({ conversation: 38, artifact: 62 })} className="workspace-resize-handle group relative z-20 w-2 shrink-0 cursor-col-resize touch-none bg-[var(--bg)] outline-none"><span className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-[var(--border)] transition-all group-hover:w-0.5 group-hover:bg-[var(--text-primary)] group-focus-visible:w-0.5" /></Separator><Panel id="artifact" minSize="42%"><div className="sim-artifact-pane h-full min-h-0">{viewer}</div></Panel></Group> : <div className="h-full lg:hidden"><div className={mobileView === "conversation" ? "h-full" : "hidden"}>{conversation}</div><div className={mobileView === "artifact" ? "h-full" : "hidden"}>{viewer}</div></div>}</div>;
  return <SimAppShell title={run.title} sessions={sidebar.sessions} missionById={sidebar.missionById} missions={sidebar.missions} currentId={run.id} loading={false} onStartMission={(missionId) => startMission(missionId)}>{content}</SimAppShell>;
}

function WorkspaceLoading() {
  return <div className="grid h-dvh place-items-center bg-[var(--bg)]"><div className="flex items-center gap-2 text-xs text-[var(--text-muted)]"><MessagesSquare className="size-4 animate-pulse" /> 正在打开 Sim 工作台…</div></div>;
}
