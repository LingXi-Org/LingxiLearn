"use client";

import { Suspense, useCallback, useEffect, useLayoutEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Group, Panel, Separator, useGroupRef, type Layout } from "react-resizable-panels";
import { Menu, MessagesSquare, PanelLeft, Shapes } from "lucide-react";
import { TaskSidebar } from "@/components/navigation/task-sidebar";
import { ArtifactWorkspace } from "@/components/workspace/artifact-workspace";
import { AgentTaskConversation } from "@/components/workspace/agent-task-conversation";
import { AgentTaskWorkspace } from "@/components/workspace/agent-task-workspace";
import { LearningConversation } from "@/components/workspace/learning-conversation";
import { useCatalogue } from "@/hooks/use-catalogue";
import { useLingxiSession } from "@/hooks/use-lingxi-session";
import { useAgentTask } from "@/hooks/use-agent-task";
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
  const taskId = mode?.kind === "task" ? mode.taskId : "";
  const { session, events, error, submitting, submit } = useLingxiSession(sessionId);
  const { task, events: agentEvents, error: agentError } = useAgentTask(taskId);
  const { sessions, missionById } = useCatalogue();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [mobileView, setMobileView] = useState<"conversation" | "artifact">("conversation");
  const [isDesktop, setIsDesktop] = useState(false);
  const groupRef = useGroupRef();

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
      <div className="grid h-dvh place-items-center bg-[var(--workspace)] p-6 text-center">
        <div><Shapes className="mx-auto size-8 text-[var(--muted-2)]" /><h1 className="mt-4 font-semibold">缺少任务参数</h1><p className="mt-2 text-xs text-[var(--muted)]">Workspace 需要真实 session id 或明确的 draft prompt。</p><Link href="/" className="mt-4 inline-flex text-xs font-medium text-[var(--brand-strong)]">返回首页</Link></div>
      </div>
    );
  }

  if (mode.kind === "task") {
    return (
      <AgentTaskLayout
        task={task}
        events={agentEvents}
        error={agentError}
        sessions={sessions}
        missionById={missionById}
        isDesktop={isDesktop}
        drawerOpen={drawerOpen}
        setDrawerOpen={setDrawerOpen}
        mobileView={mobileView}
        setMobileView={setMobileView}
      />
    );
  }

  const title = isDraft ? "未执行的任务草稿" : session?.mission.title ?? "正在载入学习任务";

  const conversation = (
    <div className="flex h-full min-h-0 flex-col bg-[#fafafa]">
      <WorkspaceHeader title={title} isDraft={isDraft} status={session?.status} onMenu={() => setDrawerOpen(true)} onArtifact={() => setMobileView("artifact")} />
      {error && <div role="alert" className="border-b border-red-100 bg-red-50 px-4 py-2 text-[11px] text-red-700">{error}</div>}
      <LearningConversation
        activity={activity}
        canSend={canSend}
        messages={messages}
        onHint={!isDraft ? () => void submit({ request_hint: true, text: "我需要提示" }) : undefined}
        onSend={handleSend}
        onWalkthrough={!isDraft ? () => void submit({ request_walkthrough: true, text: "我想看复盘" }) : undefined}
        running={!!session && session.status === "running"}
      />
    </div>
  );

  const viewer = <ArtifactWorkspace artifact={artifact} session={session} events={events} busy={submitting} submit={isDraft ? undefined : submit} onBackToConversation={() => setMobileView("conversation")} />;

  return (
    <div className="h-dvh min-h-[620px] overflow-hidden bg-[#f1f1f1]">
      {drawerOpen && (
        <div className="fixed inset-0 z-50 flex bg-black/25" onClick={() => setDrawerOpen(false)}>
          <div onClick={(event) => event.stopPropagation()}><TaskSidebar mobile sessions={sessions} missionById={missionById} currentId={sessionId} onClose={() => setDrawerOpen(false)} /></div>
        </div>
      )}

      {isDesktop ? (
      <div className="h-full">
        <Group groupRef={groupRef} orientation="horizontal" defaultLayout={{ conversation: 36, artifact: 64 }} onLayoutChanged={saveLayout}>
          <Panel id="conversation" minSize="24%" maxSize="55%">{conversation}</Panel>
          <Separator
            id="workspace-separator"
            aria-label="调整对话与工作区宽度"
            title="拖动调整宽度，双击恢复默认"
            onDoubleClick={() => groupRef.current?.setLayout({ conversation: 36, artifact: 64 })}
            className="workspace-resize-handle group relative z-20 w-2 shrink-0 cursor-col-resize touch-none bg-[#f1f1f1] outline-none transition-colors focus-visible:bg-[#5b5ce2]/10"
          >
            <span className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-[#d5d5d5] transition-all group-hover:w-0.5 group-hover:bg-[#5b5ce2] group-focus-visible:w-0.5 group-focus-visible:bg-[#5b5ce2]" />
            <span className="pointer-events-none absolute left-1/2 top-1/2 h-12 w-1 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[#5b5ce2]/0 transition-colors group-hover:bg-[#5b5ce2]/12" />
          </Separator>
          <Panel id="artifact" minSize="45%">{viewer}</Panel>
        </Group>
      </div>
      ) : (
      <div className="h-full lg:hidden">
        <div className={mobileView === "conversation" ? "h-full" : "hidden"}>{conversation}</div>
        <div className={mobileView === "artifact" ? "h-full" : "hidden"}>{viewer}</div>
      </div>
      )}
    </div>
  );
}

function AgentTaskLayout({
  task,
  events,
  error,
  sessions,
  missionById,
  isDesktop,
  drawerOpen,
  setDrawerOpen,
  mobileView,
  setMobileView,
}: {
  task: import("@/lib/types").AgentTaskSnapshot | null;
  events: import("@/lib/types").AgentTaskEvent[];
  error?: string;
  sessions: import("@/lib/types").SessionListItem[];
  missionById: Map<string, import("@/lib/types").Mission>;
  isDesktop: boolean;
  drawerOpen: boolean;
  setDrawerOpen: (value: boolean) => void;
  mobileView: "conversation" | "artifact";
  setMobileView: (value: "conversation" | "artifact") => void;
}) {
  const conversation = (
    <div className="flex h-full min-h-0 flex-col bg-[#fafafa]">
      {error && <div role="alert" className="border-b border-red-100 bg-red-50 px-4 py-2 text-[11px] text-red-700">{error}</div>}
      <AgentTaskConversation task={task} events={events} onMenu={() => setDrawerOpen(true)} onArtifact={() => setMobileView("artifact")} />
    </div>
  );
  const viewer = <AgentTaskWorkspace task={task} events={events} onBackToConversation={() => setMobileView("conversation")} />;
  return (
    <div className="h-dvh min-h-[620px] overflow-hidden bg-[#f1f1f1]">
      {drawerOpen && (
        <div className="fixed inset-0 z-50 flex bg-black/25" onClick={() => setDrawerOpen(false)}>
          <div onClick={(event) => event.stopPropagation()}><TaskSidebar mobile sessions={sessions} missionById={missionById} onClose={() => setDrawerOpen(false)} /></div>
        </div>
      )}
      {isDesktop ? (
        <div className="h-full">
          <Group orientation="horizontal" defaultLayout={{ conversation: 36, artifact: 64 }}>
            <Panel id="conversation" minSize="24%" maxSize="55%">
              <div className="relative h-full">
                <button onClick={() => setDrawerOpen(true)} className="absolute right-3 top-3 z-10 rounded-lg p-2 hover:bg-black/[.05]" aria-label="打开任务列表"><Menu className="size-4" /></button>
                {conversation}
              </div>
            </Panel>
            <Separator id="agent-workspace-separator" className="workspace-resize-handle w-2 shrink-0 cursor-col-resize bg-[#f1f1f1]" />
            <Panel id="artifact" minSize="45%">{viewer}</Panel>
          </Group>
        </div>
      ) : (
        <div className="h-full lg:hidden">
          <div className={mobileView === "conversation" ? "h-full" : "hidden"}>{conversation}</div>
          <div className={mobileView === "artifact" ? "h-full" : "hidden"}>{viewer}</div>
        </div>
      )}
    </div>
  );
}

function WorkspaceHeader({ title, isDraft, status, onMenu, onArtifact }: { title: string; isDraft: boolean; status?: string; onMenu: () => void; onArtifact: () => void }) {
  return (
    <header className="flex h-[52px] shrink-0 items-center gap-2 border-b border-[#dedede] bg-[#fafafa] px-3">
      <img src="/logo_icon.svg" alt="" className="size-7" />
      <div className="min-w-0 flex-1"><h1 className="truncate text-[15px] font-medium">{title}</h1></div>
      <button onClick={onMenu} className="grid size-8 place-items-center rounded-full hover:bg-black/[.05]" aria-label="打开任务列表"><Menu className="size-4" /></button>
      <button onClick={onArtifact} className="grid size-8 place-items-center rounded-lg bg-[var(--surface-2)] lg:hidden" aria-label="打开工作区"><PanelLeft className="size-4" /></button>
    </header>
  );
}

function WorkspaceLoading() {
  return <div className="grid h-dvh place-items-center bg-[var(--workspace)]"><div className="flex items-center gap-2 text-xs text-[var(--muted)]"><MessagesSquare className="size-4 animate-pulse" /> 正在打开学习工作台…</div></div>;
}
