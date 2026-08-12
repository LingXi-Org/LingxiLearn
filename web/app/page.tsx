"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { SimAppShell } from "@/components/sim/sim-app-shell";
import { SimComposer } from "@/components/sim/sim-composer";

export default function Home() {
  const router = useRouter();
  const sendPrompt = useCallback((prompt: string) => {
    router.push(`/workspace/?prompt=${encodeURIComponent(prompt)}`);
  }, [router]);

  return (
    <SimAppShell title="新问题">
      <section className="flex h-full min-h-0 flex-col bg-[var(--bg)]" data-testid="sim-home">
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto flex min-h-full w-full max-w-[780px] flex-col items-center justify-center px-6 pb-[22vh] pt-[2vh]">
            <div className="mb-7 text-center">
              <h1 className="text-balance text-[26px] font-medium leading-[1.15] tracking-[-0.01em] text-[var(--text-primary)] sm:text-[28px]">你想学习什么？</h1>
              <p className="mt-3 text-[13px] leading-6 text-[var(--text-secondary)]">输入问题，Lingxi 会识别意图并并行生成两份学习产物。</p>
            </div>
            <SimComposer className="max-w-none" onSubmit={sendPrompt} placeholder="输入一个知识点或学习问题…" />
            <div className="mt-4 text-center text-[11px] text-[var(--text-muted)]">任务会经过意图识别、课堂 Hook 和交互式讲解三个 Agent 阶段。</div>
          </div>
        </div>
      </section>
    </SimAppShell>
  );
}
