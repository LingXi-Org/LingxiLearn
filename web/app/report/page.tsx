"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import type { Evidence, Report, SessionSnapshot } from "@/lib/types";
import { Brand, Pill, Spinner } from "@/components/Chrome";

export default function ReportPage() {
  return (
    <Suspense fallback={<div className="h-screen grid place-items-center"><Spinner label="加载中…" /></div>}>
      <ReportView />
    </Suspense>
  );
}

function ReportView() {
  const sessionId = useSearchParams().get("id") ?? "";
  const [report, setReport] = useState<Report>();
  const [session, setSession] = useState<SessionSnapshot>();
  const [error, setError] = useState<string>();
  const [openClaim, setOpenClaim] = useState<string>();

  useEffect(() => {
    if (!sessionId) return;
    Promise.all([api.report(sessionId), api.session(sessionId)])
      .then(([r, s]) => {
        setReport(r as Report);
        setSession(s);
      })
      .catch((e) => setError(String(e.message ?? e)));
  }, [sessionId]);

  if (error)
    return (
      <div className="h-screen grid place-items-center text-[14px]" style={{ color: "var(--color-bad-500)" }}>
        {error}
      </div>
    );
  if (!report || !session)
    return (
      <div className="h-screen grid place-items-center">
        <Spinner label="正在生成学习报告…" />
      </div>
    );

  const evidence = session.evidence ?? [];
  const gain = report.learning_gain ?? 0;

  return (
    <div className="min-h-full">
      <header
        className="h-14 px-6 flex items-center gap-3 border-b"
        style={{ borderColor: "var(--line)" }}
      >
        <Brand compact />
        <span className="text-[13.5px] font-medium">学习报告</span>
        <Link
          href="/"
          className="ml-auto text-[12.5px] underline underline-offset-4 muted hover:opacity-80"
        >
          再来一个任务
        </Link>
      </header>

      <main data-testid="report-root" className="max-w-3xl mx-auto px-6 py-10 flex flex-col gap-7">
        <section className="rise">
          <span className="text-[12px] muted">{report.mission_title}</span>
          <h1 className="text-[26px] font-semibold tracking-tight leading-snug mt-1">
            {report.headline}
          </h1>
        </section>

        {/* scores */}
        <section className="grid grid-cols-3 gap-3">
          <Stat label="前测" value={`${Math.round(report.probe_score * 100)}%`} />
          <Stat label="后测" value={`${Math.round(report.verify_score * 100)}%`} />
          <Stat
            label="学习增益"
            value={`${gain > 0 ? "+" : ""}${Math.round(gain * 100)}%`}
            tone={gain > 0 ? "ok" : gain < 0 ? "bad" : "neutral"}
          />
        </section>

        {/* mastery movement */}
        <section>
          <h2 className="text-[14px] font-semibold mb-3">掌握度变化</h2>
          <div className="flex flex-col gap-3">
            {Object.keys(report.mastery_after ?? {}).sort().map((concept) => {
              const before = report.mastery_before?.[concept] ?? 0.35;
              const after = report.mastery_after[concept];
              return (
                <div key={concept}>
                  <div className="flex items-baseline justify-between mb-1">
                    <span className="mono text-[11.5px]">{concept}</span>
                    <span className="mono text-[11.5px]">
                      <span className="muted">{Math.round(before * 100)}%</span>
                      <span className="muted"> → </span>
                      <strong>{Math.round(after * 100)}%</strong>
                    </span>
                  </div>
                  <div className="h-2 rounded-full relative overflow-hidden" style={{ background: "var(--panel-2)" }}>
                    <div
                      className="absolute inset-y-0 left-0 rounded-full"
                      style={{ width: `${before * 100}%`, background: "var(--color-ink-300)" }}
                    />
                    <div
                      className="absolute inset-y-0 left-0 rounded-full"
                      style={{
                        width: `${after * 100}%`,
                        background:
                          after >= 0.7
                            ? "var(--color-ok-500)"
                            : after >= 0.45
                              ? "var(--color-warn-500)"
                              : "var(--color-bad-500)",
                        transition: "width .7s cubic-bezier(.22,1,.36,1)",
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        <ClaimList
          title="你已经掌握的"
          claims={report.strengths}
          citations={report.citations}
          evidence={evidence}
          open={openClaim}
          onOpen={setOpenClaim}
          tone="ok"
        />
        <ClaimList
          title="仍然薄弱的"
          claims={report.gaps}
          citations={report.citations}
          evidence={evidence}
          open={openClaim}
          onOpen={setOpenClaim}
          tone="warn"
        />

        {report.next_steps?.length > 0 && (
          <section>
            <h2 className="text-[14px] font-semibold mb-2.5">下一步</h2>
            <ul className="flex flex-col gap-1.5">
              {report.next_steps.map((step, i) => (
                <li key={i} className="text-[13.5px] flex gap-2">
                  <span className="muted">{i + 1}.</span>
                  <span>{step}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* step-by-step record */}
        <section>
          <h2 className="text-[14px] font-semibold mb-2.5">过程记录</h2>
          <div className="panel divide-y" style={{ borderColor: "var(--line)" }}>
            {(report.step_results ?? []).map((result) => (
              <div key={result.step_id} className="p-3 flex items-center gap-3">
                <Pill tone={result.correct ? "ok" : result.resolved === "revealed" ? "warn" : "bad"}>
                  {result.correct ? "通过" : result.resolved === "revealed" ? "复盘后理解" : "未通过"}
                </Pill>
                <span className="mono text-[12px] flex-1 truncate">{result.step_id}</span>
                <span className="mono text-[11px] muted">
                  {result.attempts} 次 · 第 {result.hint_level} 级提示
                </span>
              </div>
            ))}
          </div>
        </section>

        <footer className="text-[11.5px] muted leading-relaxed border-t pt-5" style={{ borderColor: "var(--line)" }}>
          本轮共留下 {report.evidence_count} 条可回溯证据。报告中的每一条结论都指向其中的具体条目——
          点开任意一条即可查看依据。
          <br />
          LingxiLearn 用于学习辅导与形成性反馈，不替代教师、学校或考试的最终评价。
        </footer>
      </main>
    </div>
  );
}

function Stat({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "ok" | "bad" | "neutral";
}) {
  const colors = {
    ok: "var(--color-ok-500)",
    bad: "var(--color-bad-500)",
    neutral: "var(--text)",
  };
  return (
    <div className="panel p-4 text-center">
      <span className="block text-[11.5px] muted">{label}</span>
      <span className="mono block text-[24px] font-semibold mt-1" style={{ color: colors[tone] }}>
        {value}
      </span>
    </div>
  );
}

function ClaimList({
  title,
  claims,
  citations,
  evidence,
  open,
  onOpen,
  tone,
}: {
  title: string;
  claims: string[];
  citations: Record<string, string[]>;
  evidence: Evidence[];
  open?: string;
  onOpen: (claim?: string) => void;
  tone: "ok" | "warn";
}) {
  if (!claims?.length) return null;
  const accent = tone === "ok" ? "var(--color-ok-500)" : "var(--color-warn-500)";
  return (
    <section>
      <h2 className="text-[14px] font-semibold mb-2.5">{title}</h2>
      <div className="flex flex-col gap-2">
        {claims.map((claim) => {
          const ids = citations?.[claim] ?? [];
          const isOpen = open === claim;
          return (
            <div key={claim} className="panel overflow-hidden">
              <button
                onClick={() => onOpen(isOpen ? undefined : claim)}
                className="w-full text-left p-3 flex items-start gap-2.5"
              >
                <span className="w-1 self-stretch rounded-full shrink-0" style={{ background: accent }} />
                <span className="text-[13.5px] leading-relaxed flex-1">{claim}</span>
                {ids.length > 0 && (
                  <span className="mono text-[10.5px] muted shrink-0 mt-0.5">
                    {ids.length} 条依据 {isOpen ? "▴" : "▾"}
                  </span>
                )}
              </button>
              {isOpen && ids.length > 0 && (
                <div className="px-3 pb-3 pt-0 flex flex-col gap-1.5 rise">
                  {ids.map((id) => {
                    const item = evidence.find((e) => e.id === id);
                    return (
                      <div
                        key={id}
                        className="p-2 rounded-[8px] text-[12px]"
                        style={{ background: "var(--panel-2)" }}
                      >
                        <span className="mono text-[10px] muted">{id}</span>
                        <span className="block mt-0.5">{item?.summary ?? "（证据已不可用）"}</span>
                        {item && <span className="mono block text-[10px] muted mt-0.5">{item.source}</span>}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
