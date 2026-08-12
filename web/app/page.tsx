"use client";

import { useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { SimAppShell, markSimLayoutTransition } from "@/components/sim/sim-app-shell";
import { SimComposer } from "@/components/sim/sim-composer";
import { mockSidebarData } from "@/lib/sim-mock";

export default function Home() {
  const router = useRouter();
  const sidebar = useMemo(() => mockSidebarData(), []);
  const sendPrompt = useCallback((prompt: string) => {
    markSimLayoutTransition();
    router.push(`/workspace/?mock=1&prompt=${encodeURIComponent(prompt)}`);
  }, [router]);
  const startMission = useCallback((missionId: string) => {
    const mission = sidebar.missionById.get(missionId);
    markSimLayoutTransition();
    router.push(`/workspace/?mock=1&prompt=${encodeURIComponent(mission?.title ?? "Sim workflow placeholder")}`);
  }, [router, sidebar.missionById]);

  return (
    <SimAppShell title="New chat" sessions={sidebar.sessions} missionById={sidebar.missionById} missions={sidebar.missions} loading={false} onStartMission={(missionId) => startMission(missionId)}>
      <section className="flex h-full min-h-0 flex-col bg-[var(--bg)]" data-testid="sim-home">
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto flex min-h-full w-full max-w-[780px] flex-col items-center justify-center px-6 pb-[22vh] pt-[2vh]">
            <div className="mb-7 text-center">
              <h1 className="text-balance text-[26px] font-medium leading-[1.15] tracking-[-0.01em] text-[var(--text-primary)] sm:text-[28px]">What do you want to learn?</h1>
              <p className="mt-3 text-[13px] leading-6 text-[var(--text-secondary)]">Sim 原生工作区演示 · 所有 Agent 输出均为占位实现。</p>
            </div>
            <SimComposer className="max-w-none" onSubmit={sendPrompt} placeholder="Ask anything or describe a learning goal…" />
            <div className="mt-4 text-center text-[11px] text-[var(--text-muted)]">发送后将显示占位 Agent 输出、编排图和 Sim 原生能力占位。</div>
          </div>
        </div>
      </section>
    </SimAppShell>
  );
}
