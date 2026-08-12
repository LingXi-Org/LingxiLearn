"use client";

import { useCallback, useMemo, useState } from "react";
import { CircleAlert, Code2, Hammer, RefreshCw, Wrench } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { LearningPrompt } from "@/components/workspace/learning-conversation";
import { markSimLayoutTransition, SimAppShell } from "@/components/sim/sim-app-shell";
import { useCatalogue } from "@/hooks/use-catalogue";
import { isCatalogueMissionVisible } from "@/lib/catalogue-visibility";

const QUICK_ACTIONS: Array<{ title: string; icon: LucideIcon; tone: string }> = [
  { title: "探索并理解代码", icon: Code2, tone: "bg-sky-50 text-sky-600" },
  { title: "构建新功能、应用或工具", icon: Hammer, tone: "bg-violet-50 text-violet-600" },
  { title: "审查代码并提出修改建议", icon: RefreshCw, tone: "bg-emerald-50 text-emerald-600" },
  { title: "修复问题和失败", icon: Wrench, tone: "bg-orange-50 text-orange-600" },
];

export default function Home() {
  const router = useRouter();
  const { packs, sessions, missionById, error, loading, createSession, createAgentTask } = useCatalogue();
  const [starting, setStarting] = useState<string>();
  const [startingPrompt, setStartingPrompt] = useState(false);
  const [promptError, setPromptError] = useState<string>();

  const availableMissions = useMemo(
    () => packs.flatMap((pack) => pack.missions
      .filter((mission) => isCatalogueMissionVisible(mission.id))
      .map((mission) => ({ mission, packId: pack.id }))),
    [packs],
  );

  const openDraft = useCallback(async (prompt: string) => {
    setStartingPrompt(true);
    setPromptError(undefined);
    try {
      const created = await createAgentTask(prompt);
      markSimLayoutTransition();
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
      markSimLayoutTransition();
      router.push(`/workspace/?id=${encodeURIComponent(created.id)}`);
    } finally {
      setStarting(undefined);
    }
  }, [createSession, router]);

  return (
    <SimAppShell title="新对话" sessions={sessions} missionById={missionById} missions={availableMissions} loading={loading} starting={starting} onStartMission={(missionId, packId) => void startMission(missionId, packId)}>
      <section className="sim-empty-canvas flex h-full min-h-0 flex-col bg-[var(--bg)]">
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto flex min-h-full w-full max-w-[1120px] flex-col justify-end px-4 pb-4 pt-12 sm:px-8 sm:pb-8">
            <div className="pb-7 text-center sm:pb-9">
              <h1 data-testid="home-greeting" className="text-[25px] font-medium tracking-[-0.035em] text-[var(--text-primary)] sm:text-[32px]">欢迎回来，今天想完成什么？</h1>
              <p className="mt-3 text-[13px] leading-6 text-[var(--text-secondary)]">把学习目标、代码问题或新想法交给我。</p>
            </div>
            <div className="grid gap-3 pb-4 sm:grid-cols-2 lg:grid-cols-4">
              {QUICK_ACTIONS.map(({ title, icon: Icon, tone }) => <div key={title} className="flex min-h-[132px] flex-col justify-between rounded-[17px] border border-[#dedede] bg-white p-4 transition-colors hover:border-[#c9c9c9] hover:bg-[#fdfdfd] sm:p-5" aria-label={title}><span className={`grid size-9 place-items-center rounded-xl ${tone}`}><Icon className="size-[18px]" strokeWidth={1.7} /></span><span className="max-w-[210px] text-left text-[14px] font-medium leading-6 text-[var(--text-primary)] sm:text-[15px]">{title}</span></div>)}
            </div>
            <div className="w-full">
              {error && <div role="alert" className="mb-3 flex items-start gap-2 border border-red-200 bg-red-50 px-3 py-2.5 text-[12px] text-red-700"><CircleAlert className="mt-0.5 size-3.5 shrink-0" /><span>课程目录暂时无法加载，请检查后端服务。</span></div>}
              {promptError && <div role="alert" className="mb-3 border border-red-200 bg-red-50 px-3 py-2.5 text-[12px] text-red-700">{promptError}</div>}
              <LearningPrompt className="max-w-none" onSend={openDraft} disabled={startingPrompt} placeholder={startingPrompt ? "正在调度 Agent…" : "输入你的问题或学习目标…"} />
            </div>
          </div>
        </div>
      </section>
    </SimAppShell>
  );
}
