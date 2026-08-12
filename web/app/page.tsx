"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { SimAppShell } from "@/components/sim/sim-app-shell";
import { SimComposer } from "@/components/sim/sim-composer";
import { ThinkingLoader } from "@/components/sim/source/thinking-loader";

export default function Home() {
  const router = useRouter();
  const [transitionPhase, setTransitionPhase] = useState<"idle" | "split" | "thinking">("idle");
  const [pendingPrompt, setPendingPrompt] = useState("");
  const sendPrompt = useCallback((prompt: string) => {
    setPendingPrompt(prompt);
    setTransitionPhase("split");
    window.setTimeout(() => setTransitionPhase("thinking"), 760);
    window.setTimeout(() => router.push(`/workspace/?prompt=${encodeURIComponent(prompt)}`), 2550);
  }, [router]);

  return (
    <SimAppShell title="新问题">
      <section className="home-transition-shell flex h-full min-h-0 flex-col bg-[var(--bg)]" data-testid="sim-home" data-transitioning={transitionPhase !== "idle"} data-phase={transitionPhase}>
        <div className="home-transition-content min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto flex min-h-full w-full max-w-[780px] flex-col items-center justify-center px-6 pb-[22vh] pt-[2vh]">
            <div className="mb-7 text-center">
              <h1 className="text-balance text-[26px] font-medium leading-[1.15] tracking-[-0.01em] text-[var(--text-primary)] sm:text-[28px]">你想学习什么？</h1>
              <p className="mt-3 text-[13px] leading-6 text-[var(--text-secondary)]">输入问题，Lingxi 会识别意图并并行生成两份学习产物。</p>
            </div>
            <SimComposer className="max-w-none" onSubmit={sendPrompt} placeholder="输入一个知识点或学习问题…" isSending={transitionPhase !== "idle"} disabled={transitionPhase !== "idle"} />
            <div className="mt-4 text-center text-[11px] text-[var(--text-muted)]">任务会经过意图识别、课堂 Hook 和交互式讲解三个 Agent 阶段。</div>
          </div>
        </div>
        {transitionPhase !== "idle" && <>
          <div className="home-transition-preview" aria-hidden="true">
            <div><div className="home-transition-preview-line" /><div className="home-transition-preview-line" /><div className="home-transition-preview-line" /></div>
            <div><div className="home-transition-preview-card" /></div>
          </div>
          <div className="home-transition-loader" aria-live="polite" aria-label={pendingPrompt ? `正在准备：${pendingPrompt}` : "正在准备工作区"}><ThinkingLoader size={30} /></div>
        </>}
      </section>
    </SimAppShell>
  );
}
