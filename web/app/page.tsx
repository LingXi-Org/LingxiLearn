"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Activity, ArrowUpRight, BookOpen, Compass, Library, Menu, Network } from "lucide-react";
import { LearningPrompt } from "@/components/workspace/learning-conversation";
import { TaskSidebar } from "@/components/navigation/task-sidebar";
import { Button } from "@/components/ui/button";
import { useCatalogue } from "@/hooks/use-catalogue";
import type { Mission, SessionListItem } from "@/lib/types";
const GREETINGS = [
  "今天想学点什么？",
  "有什么想一起弄懂的？",
  "准备好开始今天的学习了吗？",
  "今天从哪个问题开始？",
];

export default function Home() {
  const router = useRouter();
  const { packs, sessions, missionById, error, loading, createSession, createAgentTask } = useCatalogue();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [starting, setStarting] = useState<string>();
  const [activeTab, setActiveTab] = useState<"discover" | "mine">("discover");
  const [greeting, setGreeting] = useState(GREETINGS[0]);

  useEffect(() => {
    setGreeting(GREETINGS[Math.floor(Math.random() * GREETINGS.length)]);
  }, []);

  const [startingPrompt, setStartingPrompt] = useState(false);
  const [promptError, setPromptError] = useState<string>();

  const openDraft = useCallback(async (prompt: string) => {
    setStartingPrompt(true);
    setPromptError(undefined);
    try {
      const created = await createAgentTask(prompt);
      router.push(`/workspace/?task=${encodeURIComponent(created.id)}`);
    } catch (cause) {
      setPromptError(cause instanceof Error ? cause.message : "Agent Task 创建失败，请稍后重试。");
    } finally {
      setStartingPrompt(false);
    }
  }, [createAgentTask, router]);

  const startMission = useCallback(async (missionId: string, packId: string) => {
    setStarting(missionId);
    try {
      const created = await createSession(missionId, packId);
      router.push(`/workspace/?id=${encodeURIComponent(created.id)}`);
    } finally {
      setStarting(undefined);
    }
  }, [createSession, router]);

  const availableMissions = useMemo(
    () => packs.flatMap((pack) => pack.missions.map((mission) => ({ mission, packId: pack.id }))),
    [packs],
  );

  return (
    <div className="flex h-dvh min-h-[640px] w-full max-w-full overflow-hidden bg-[#f5f5f5]">
      <div className="hidden lg:block">
        <TaskSidebar sessions={sessions} missionById={missionById} />
      </div>

      {sidebarOpen && (
        <div className="fixed inset-0 z-50 flex bg-black/25 lg:hidden" onClick={() => setSidebarOpen(false)}>
          <div onClick={(event) => event.stopPropagation()}>
            <TaskSidebar mobile sessions={sessions} missionById={missionById} onClose={() => setSidebarOpen(false)} />
          </div>
        </div>
      )}

      <main className="home-canvas relative min-w-0 flex-1 overflow-x-hidden overflow-y-auto bg-white lg:mt-[3px] lg:rounded-tl-[28px]">
        <HomeBackdrop />
        <header className="flex h-14 items-center px-4 lg:hidden">
          <button onClick={() => setSidebarOpen(true)} className="grid size-9 place-items-center rounded-xl hover:bg-[var(--surface-2)]" aria-label="打开任务列表">
            <Menu className="size-5" />
          </button>
        </header>

        <div className="home-center relative z-10 mx-auto px-4 pb-16 sm:px-6 lg:px-0">
          <section className="mx-auto max-w-[1064px]">
            <div className="flex items-center justify-center gap-4 sm:gap-5">
              <img src="/logo_icon.svg" alt="" className="size-10 shrink-0 sm:size-12 lg:size-[50px]" />
              <h1 data-testid="home-greeting" className="home-title text-balance font-semibold leading-none tracking-[-0.035em] text-[#202020]">
                {greeting}
              </h1>
            </div>

          <LearningPrompt className="home-learning-prompt mt-7 sm:mt-10 lg:mt-12" onSend={openDraft} disabled={startingPrompt} placeholder={startingPrompt ? "正在调度 Agent…" : "描述你想学习的内容或遇到的问题"} />
          {promptError && <p role="alert" className="mx-auto mt-3 max-w-xl text-center text-xs text-red-600">{promptError}</p>}
          </section>

          <section id="courses" className="mt-8 sm:mt-10" aria-label="课程">
            <div role="tablist" aria-label="课程分类" className="mx-auto flex w-fit items-center gap-8 border-b border-[#dedede] px-4">
              <button
                role="tab"
                aria-selected={activeTab === "discover"}
                onClick={() => setActiveTab("discover")}
                className={`relative flex h-12 items-center gap-2 px-2 text-[16px] transition-colors ${activeTab === "discover" ? "font-semibold text-[var(--ink)] after:absolute after:inset-x-0 after:-bottom-px after:h-[3px] after:rounded-full after:bg-[var(--ink)]" : "text-[var(--muted)] hover:text-[var(--ink)]"}`}
              >
                <Compass className="size-[18px]" /> 课程发现
              </button>
              <button
                role="tab"
                aria-selected={activeTab === "mine"}
                onClick={() => setActiveTab("mine")}
                className={`relative flex h-12 items-center gap-2 px-2 text-[16px] transition-colors ${activeTab === "mine" ? "font-semibold text-[var(--ink)] after:absolute after:inset-x-0 after:-bottom-px after:h-[3px] after:rounded-full after:bg-[var(--ink)]" : "text-[var(--muted)] hover:text-[var(--ink)]"}`}
              >
                <Library className="size-[18px]" /> 我的课程
              </button>
            </div>

            {error && <div role="alert" className="mt-8 text-center text-sm text-red-600">课程暂时无法加载，请稍后再试。</div>}

            {activeTab === "discover" ? (
              <div className="mt-[31px] grid gap-5 md:grid-cols-2">
                {loading && !availableMissions.length && [0, 1].map((item) => <div key={item} className="h-[330px] animate-pulse rounded-[28px] bg-white/70 shadow-sm" />)}
                {availableMissions.map(({ mission, packId }, index) => (
                  <DiscoveryCard
                    key={mission.id}
                    mission={mission}
                    index={index}
                    loading={starting === mission.id}
                    disabled={!!starting}
                    onStart={() => void startMission(mission.id, packId)}
                  />
                ))}
              </div>
            ) : (
              <MyCourses sessions={sessions} missionById={missionById} onDiscover={() => setActiveTab("discover")} />
            )}
          </section>
        </div>
      </main>
    </div>
  );
}

function HomeBackdrop() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      <div className="absolute left-[24%] top-[6%] h-[300px] w-[520px] rounded-full bg-indigo-50/55 blur-[125px]" />
      <div className="absolute right-[2%] top-[28%] size-[400px] rounded-full bg-slate-100/55 blur-[135px]" />
    </div>
  );
}

function DiscoveryCard({ mission, index, loading, disabled, onStart }: { mission: Mission; index: number; loading: boolean; disabled: boolean; onStart: () => void }) {
  return (
    <button
      type="button"
      onClick={onStart}
      disabled={disabled}
      data-testid={`start-mission-${mission.id}`}
      aria-label={`开始课程：${mission.title}`}
      className="group relative min-h-[306px] overflow-hidden rounded-[20px] border border-[#dedede] bg-white text-left shadow-[0_10px_28px_rgba(0,0,0,.045)] transition duration-300 hover:-translate-y-1 hover:border-[#c8c8c8] hover:shadow-[0_16px_38px_rgba(0,0,0,.07)] disabled:translate-y-0"
    >
      <CoursePreview index={index} />
      <div className="relative flex min-h-[102px] items-center gap-4 px-6 py-4 sm:px-7">
        <div className="min-w-0 flex-1">
          <h2 className="text-[21px] font-semibold tracking-[-0.035em] text-[var(--ink)] sm:text-[23px]">{mission.title}</h2>
          <p className="mt-1 line-clamp-1 text-sm text-[var(--muted)]">{loading ? "正在打开课程…" : mission.subtitle}</p>
        </div>
        <span className="grid size-11 shrink-0 place-items-center rounded-full border border-[#dedede] bg-[#f7f7f7] text-[#333] transition-all group-hover:bg-[#202020] group-hover:text-white">
          <ArrowUpRight className="size-5" />
        </span>
      </div>
    </button>
  );
}

function CoursePreview({ index }: { index: number }) {
  if (index % 2 === 0) {
    return (
      <div className="relative h-[204px] overflow-hidden bg-[radial-gradient(circle_at_78%_12%,rgba(151,162,255,.85),transparent_34%),linear-gradient(135deg,#202a53,#5364a6)]">
        <div className="absolute -bottom-24 -left-10 size-64 rounded-full border border-white/10" />
        <div className="absolute -bottom-14 left-14 size-52 rounded-full border border-white/10" />
        <div className="absolute left-6 top-6 w-[42%] rounded-2xl border border-white/15 bg-white/12 p-4 shadow-xl backdrop-blur-md">
          {["w-4/5", "w-3/5", "w-full"].map((width, row) => (
            <div key={width} className="mb-3 flex items-center gap-2 last:mb-0">
              <span className={`size-2 rounded-full ${row === 0 ? "bg-indigo-200" : row === 1 ? "bg-sky-200" : "bg-violet-200"}`} />
              <span className={`h-1.5 rounded-full bg-white/50 ${width}`} />
            </div>
          ))}
        </div>
        <div className="absolute right-[11%] top-[28%] grid size-24 place-items-center rounded-3xl border border-white/20 bg-white/15 shadow-2xl backdrop-blur-lg">
          <Network className="size-10 text-white" strokeWidth={1.4} />
        </div>
        <span className="absolute left-[44%] top-[47%] h-px w-[22%] rotate-[-8deg] bg-white/35" />
      </div>
    );
  }
  return (
    <div className="relative h-[204px] overflow-hidden bg-[radial-gradient(circle_at_74%_10%,rgba(183,235,220,.9),transparent_34%),linear-gradient(135deg,#31575b,#76a698)]">
      <div className="absolute inset-x-6 bottom-5 top-5 rounded-[22px] border border-white/15 bg-[#17343a]/45 shadow-2xl backdrop-blur-sm">
        <div className="absolute inset-x-5 top-5 flex h-8 items-end gap-1.5">
          {[35, 48, 28, 62, 44, 74, 54, 82, 48, 66, 38, 58].map((height, item) => (
            <span key={item} className="flex-1 rounded-t-full bg-emerald-100/65" style={{ height: `${height}%` }} />
          ))}
        </div>
        <div className="absolute inset-x-5 bottom-5 top-[76px] overflow-hidden rounded-xl border border-white/10 bg-black/10">
          <Activity className="absolute left-1/2 top-1/2 size-20 -translate-x-1/2 -translate-y-1/2 text-white/85" strokeWidth={1.1} />
          <div className="absolute inset-x-4 bottom-3 h-px bg-white/20" />
        </div>
      </div>
    </div>
  );
}

function MyCourses({ sessions, missionById, onDiscover }: { sessions: SessionListItem[]; missionById: Map<string, Mission>; onDiscover: () => void }) {
  if (sessions.length === 0) {
    return (
      <div className="mt-7 grid min-h-[286px] place-items-center rounded-[28px] border border-[var(--line-soft)] bg-white/70 text-center">
        <div>
          <BookOpen className="mx-auto size-9 text-[var(--muted-2)]" strokeWidth={1.5} />
          <h2 className="mt-4 text-lg font-semibold">还没有课程</h2>
          <Button variant="outline" className="mt-5" onClick={onDiscover}>去发现课程</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-7 grid gap-4 md:grid-cols-2">
      {sessions.map((session, index) => {
        const mission = missionById.get(session.mission_id);
        return (
          <a
            key={session.id}
            href={`/workspace/?id=${encodeURIComponent(session.id)}`}
            className={`group relative min-h-[220px] overflow-hidden rounded-[28px] p-6 text-white transition duration-300 hover:-translate-y-1 ${index % 2 === 0 ? "bg-gradient-to-br from-[#303b68] to-[#6373b5]" : "bg-gradient-to-br from-[#34585a] to-[#74a291]"}`}
          >
            <BookOpen className="absolute right-8 top-8 size-16 text-white/20" strokeWidth={1.25} />
            <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/45 to-transparent p-6 pt-16">
              <h2 className="text-xl font-semibold">{mission?.title ?? "学习课程"}</h2>
              <p className="mt-1 text-sm text-white/75">继续学习</p>
            </div>
          </a>
        );
      })}
    </div>
  );
}
