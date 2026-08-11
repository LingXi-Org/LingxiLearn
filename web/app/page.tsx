"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Mission, Pack } from "@/lib/types";
import { Brand, BrainBadge, Pill, Spinner } from "@/components/Chrome";

export default function Home() {
  const router = useRouter();
  const [packs, setPacks] = useState<Pack[]>([]);
  const [brain, setBrain] = useState<string>();
  const [error, setError] = useState<string>();
  const [starting, setStarting] = useState<string>();

  useEffect(() => {
    Promise.all([api.packs(), api.health()])
      .then(([p, h]) => {
        setPacks(p.packs);
        setBrain(h.brain);
      })
      .catch((e) => setError(String(e.message ?? e)));
  }, []);

  async function begin(mission: Mission, packId: string) {
    setStarting(mission.id);
    try {
      const stored = localStorage.getItem("lingxilearn.learner") ?? "";
      const created = await api.createSession(mission.id, packId, stored);
      localStorage.setItem("lingxilearn.learner", created.learner_id);
      router.push(`/classroom/?id=${created.id}`);
    } catch (e: any) {
      setError(String(e.message ?? e));
      setStarting(undefined);
    }
  }

  return (
    <div className="min-h-full">
      <header className="flex items-center justify-between px-6 sm:px-10 h-16">
        <Brand />
        <BrainBadge brain={brain} />
      </header>

      <main className="px-6 sm:px-10 pb-20 max-w-5xl mx-auto">
        <section className="pt-10 pb-9 rise">
          <h1 className="text-[30px] sm:text-[38px] font-semibold tracking-tight leading-[1.15]">
            今天想解决什么工程问题？
          </h1>
          <p className="mt-3 text-[15px] muted max-w-2xl leading-relaxed">
            LingxiLearn 不替你做题。它会读懂你现在的状态，调用真实工具处理真实工件，
            用问题把你引到结论跟前，再验证你是不是真的会了——整个过程留下可回溯的证据。
          </p>
        </section>

        {error && (
          <div
            className="panel p-4 mb-6 text-[13px]"
            style={{ borderColor: "var(--color-bad-500)" }}
          >
            <strong className="font-medium">连接后端失败：</strong> {error}
            <p className="muted mt-1">请确认服务已启动（默认 http://localhost:8000）。</p>
          </div>
        )}

        {!packs.length && !error && (
          <div className="panel p-10 grid place-items-center">
            <Spinner label="正在加载课程包…" />
          </div>
        )}

        {packs.map((pack) => (
          <section key={pack.id} className="mb-10">
            <div className="flex items-baseline gap-3 mb-4">
              <h2 className="text-[17px] font-semibold">{pack.title}</h2>
              <span className="mono text-[11px] muted">
                {pack.id} · v{pack.version}
              </span>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              {pack.missions.map((mission, index) => (
                <article
                  key={mission.id}
                  className="panel p-5 flex flex-col rise transition-shadow hover:shadow-md"
                  style={{ animationDelay: `${index * 60}ms` }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-[16px] font-semibold leading-snug">{mission.title}</h3>
                      <p className="text-[12.5px] muted mt-0.5">{mission.subtitle}</p>
                    </div>
                    <Pill tone="neutral">约 {mission.estimated_minutes} 分钟</Pill>
                  </div>

                  <p className="text-[13px] mt-3 leading-relaxed" style={{ color: "var(--muted)" }}>
                    {mission.summary}
                  </p>

                  {mission.why_not_chat && (
                    <div
                      className="mt-3.5 p-3 rounded-[10px] text-[12.5px] leading-relaxed"
                      style={{
                        background: "color-mix(in oklab, var(--color-accent-500) 8%, transparent)",
                      }}
                    >
                      <span
                        className="font-medium"
                        style={{ color: "var(--color-accent-600)" }}
                      >
                        为什么这件事不能靠对话框完成
                      </span>
                      <p className="mt-1 muted">{mission.why_not_chat}</p>
                    </div>
                  )}

                  <div className="flex flex-wrap gap-1.5 mt-4">
                    {mission.concepts.map((c) => (
                      <span
                        key={c}
                        className="mono text-[10.5px] px-1.5 py-0.5 rounded"
                        style={{ background: "var(--panel-2)", color: "var(--muted)" }}
                      >
                        {c}
                      </span>
                    ))}
                  </div>

                  <button
                    onClick={() => begin(mission, pack.id)}
                    disabled={!!starting}
                    className="mt-5 w-full h-10 rounded-[10px] font-medium text-[14px] text-white transition-colors disabled:opacity-60"
                    style={{ background: "var(--color-accent-500)" }}
                  >
                    {starting === mission.id ? "正在准备…" : "开始"}
                  </button>
                </article>
              ))}
            </div>
          </section>
        ))}

        <footer className="mt-14 pt-6 text-[11.5px] muted leading-relaxed border-t"
          style={{ borderColor: "var(--line)" }}>
          LingxiLearn 用于学习辅导与形成性反馈，不替代教师、学校或考试的最终评价。
          演示用抓包与学习记录均为合成数据。
        </footer>
      </main>
    </div>
  );
}
