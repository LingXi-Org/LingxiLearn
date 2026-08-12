"use client";

import { Suspense, useCallback, useEffect, useLayoutEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Group, Panel, Separator, useGroupRef, type Layout } from "react-resizable-panels";
import { MessagesSquare, PanelLeft, Shapes } from "lucide-react";
import { consumeSimLayoutTransition, SimAppShell } from "@/components/sim/sim-app-shell";
import { ArtifactWorkspace } from "@/components/workspace/artifact-workspace";
import { LearningConversation } from "@/components/workspace/learning-conversation";
import { useCatalogue } from "@/hooks/use-catalogue";
import { useLingxiSession } from "@/hooks/use-lingxi-session";
import { isCatalogueMissionVisible } from "@/lib/catalogue-visibility";
import {
  deriveArtifact,
  draftMessages,
  makeDraftArtifact,
  parseWorkspaceMode,
  reduceAgentActivity,
  transcriptToMessages,
  type AgentActivity,
  type ArtifactDescriptor,
  type WorkspaceMessage,
} from "@/lib/workspace";

const LAYOUT_KEY = "lingxilearn.workspace.layout";

export default function WorkspacePage() {
  return <Suspense fallback={<WorkspaceLoading />}><Workspace /></Suspense>;
}

function Workspace() {
  const params = useSearchParams();
  const mode = useMemo(() => parseWorkspaceMode(new URLSearchParams(params.toString())), [params]);
  const sessionId = mode?.kind === "session" ? mode.sessionId : "";
  const { session, events, error, submitting, submit } = useLingxiSession(sessionId);
  const { packs, sessions, missionById, loading } = useCatalogue();
  const [mobileView, setMobileView] = useState<"conversation" | "artifact">("conversation");
  const [isDesktop, setIsDesktop] = useState(false);
  const [layoutReady, setLayoutReady] = useState(false);
  const groupRef = useGroupRef();

  const availableMissions = useMemo(
    () => packs.flatMap((pack) => pack.missions
      .filter((mission) => isCatalogueMissionVisible(mission.id))
      .map((mission) => ({ mission, packId: pack.id }))),
    [packs],
  );

  useEffect(() => {
    const shouldAnimate = consumeSimLayoutTransition();
    if (!shouldAnimate) {
      setLayoutReady(true);
      return;
    }
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

  const saveLayout = useCallback((layout: Layout) => {
    window.localStorage.setItem(LAYOUT_KEY, JSON.stringify(layout));
  }, []);

  const isDraft = mode?.kind === "draft";
  const messages = useMemo<WorkspaceMessage[]>(() => {
    if (mode?.kind === "draft") return draftMessages(mode.prompt);
    return session ? transcriptToMessages(session.transcript ?? []) : [];
  }, [mode, session]);

  const draftActivity = useMemo<AgentActivity>(() => ({
    plan: [], activeStep: undefined, tools: [], evidence: [], running: false,
    summary: "这只是任务草稿：后端尚未创建任务，也没有 Agent 或工具正在执行。",
  }), []);
  const activity = useMemo(() => isDraft ? draftActivity : reduceAgentActivity(events, session), [draftActivity, events, isDraft, session]);

  const artifact = useMemo<ArtifactDescriptor>(() => {
    if (mode?.kind === "draft") return makeDraftArtifact(mode.prompt);
    if (session) return deriveArtifact(session);
    return { id: "loading", kind: "empty", title: "App Viewer", source: "api", status: error ? "error" : "running", revision: 0, description: error ? "会话加载失败，请返回首页重试。" : "正在读取任务状态与 Artifact。" };
  }, [error, mode, session]);

  const pendingKind = session?.pending?.value.kind;
  const canSend = !!session && pendingKind === "answer" && !submitting;
  const handleSend = useCallback(async (text: string) => {
    if (canSend) await submit({ text });
  }, [canSend, submit]);

  if (!mode) {
    return (
      <div className="grid h-dvh place-items-center bg-[var(--bg)] p-6 text-center">
        <div><Shapes className="mx-auto size-8 text-[var(--text-icon)]" /><h1 className="mt-4 font-medium">缺少任务参数</h1><p className="mt-2 text-xs text-[var(--text-muted)]">Workspace 需要真实 session id 或明确的 draft prompt。</p><Link href="/" className="mt-4 inline-flex text-xs font-medium text-[var(--text-primary)]">返回首页</Link></div>
      </div>
    );
  }

  const title = isDraft ? "未执行的任务草稿" : session?.mission.title ?? "正在载入学习任务";

  const conversation = (
    <div className="flex h-full min-h-0 flex-col bg-[var(--bg)]">
      <WorkspaceHeader title={title} isDraft={isDraft} status={session?.status} onArtifact={() => setMobileView("artifact")} />
      {error && <div role="alert" className="border-b border-red-200 bg-red-50 px-4 py-2 text-[11px] text-red-700">{error}</div>}
      <LearningConversation
        activity={activity}
        canSend={canSend}
        messages={messages}
        onSend={handleSend}
        running={!!session && session.status === "running"}
      />
    </div>
  );

  const viewer = <ArtifactWorkspace artifact={artifact} session={session} events={events} busy={submitting} submit={isDraft ? undefined : submit} onBackToConversation={() => setMobileView("conversation")} />;

  return (
    <SimAppShell title={title} sessions={sessions} missionById={missionById} missions={availableMissions} loading={loading} currentId={sessionId}>
      <div className={layoutReady ? "sim-three-column-layout sim-layout-ready h-full min-h-0 bg-[var(--bg)]" : "sim-three-column-layout sim-layout-entering h-full min-h-0 bg-[var(--bg)]"}>
        {isDesktop ? (
          <Group groupRef={groupRef} orientation="horizontal" defaultLayout={{ conversation: 38, artifact: 62 }} onLayoutChanged={saveLayout}>
            <Panel id="conversation" minSize="28%" maxSize="58%"><div className="sim-conversation-pane h-full min-h-0">{conversation}</div></Panel>
            <Separator
              id="workspace-separator"
              aria-label="调整对话与工作区宽度"
              title="拖动调整宽度，双击恢复默认"
              onDoubleClick={() => groupRef.current?.setLayout({ conversation: 38, artifact: 62 })}
              className="workspace-resize-handle group relative z-20 w-2 shrink-0 cursor-col-resize touch-none bg-[var(--bg)] outline-none transition-colors focus-visible:bg-[var(--surface-5)]"
            >
              <span className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-[var(--border)] transition-all group-hover:w-0.5 group-hover:bg-[var(--text-primary)] group-focus-visible:w-0.5" />
              <span className="pointer-events-none absolute left-1/2 top-1/2 h-12 w-1 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[var(--text-primary)]/0 transition-colors group-hover:bg-[var(--text-primary)]/10" />
            </Separator>
            <Panel id="artifact" minSize="42%"><div className="sim-artifact-pane h-full min-h-0">{viewer}</div></Panel>
          </Group>
        ) : (
          <div className="h-full lg:hidden">
            <div className={mobileView === "conversation" ? "h-full" : "hidden"}>{conversation}</div>
            <div className={mobileView === "artifact" ? "h-full" : "hidden"}>{viewer}</div>
          </div>
        )}
      </div>
    </SimAppShell>
  );
}

function WorkspaceHeader({ title, isDraft, status, onArtifact }: { title: string; isDraft: boolean; status?: string; onArtifact: () => void }) {
  return (
    <header className="flex h-11 shrink-0 items-center gap-2 border-b border-[var(--border)] bg-[var(--surface-1)] px-3 sm:px-4 lg:hidden">
      <span className="size-1.5 rounded-full bg-[var(--brand)]" aria-hidden="true" />
      <div className="min-w-0 flex-1"><h1 className="truncate text-[12px] font-medium">{title}</h1><p className="text-[10px] text-[var(--text-muted)]">{isDraft ? "draft · 未连接后端任务" : status ?? "loading"}</p></div>
      <button onClick={onArtifact} className="grid size-7 place-items-center rounded-md bg-[var(--surface-5)] text-[var(--text-icon)] lg:hidden" aria-label="打开工作区"><PanelLeft className="size-3.5" /></button>
    </header>
  );
}

function WorkspaceLoading() {
  return <div className="grid h-dvh place-items-center bg-[var(--bg)]"><div className="flex items-center gap-2 text-xs text-[var(--text-muted)]"><MessagesSquare className="size-4 animate-pulse" /> 正在打开学习工作台…</div></div>;
}
