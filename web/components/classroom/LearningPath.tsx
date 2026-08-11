"use client";

import type { MasteryChange, SessionSnapshot } from "@/lib/types";

const PHASE_LABEL: Record<string, string> = {
  intake: "准备",
  diagnose: "前测诊断",
  plan: "生成路径",
  investigate: "调用工具",
  coach: "教练提问",
  await_learner: "等你作答",
  judge: "判定",
  advance: "更新掌握度",
  verify: "后测",
  report: "生成报告",
  done: "已完成",
};

/**
 * Left rail: where the learner is, and what the system believes about them.
 *
 * The plan is rendered from the session's own `plan`, which is chosen from
 * mastery at run time — so a learner who already knows the warm-up sees a
 * shorter list than one who doesn't. Personalisation you can point at.
 */
export function LearningPath({
  session,
  onOpenMastery,
}: {
  session: SessionSnapshot;
  onOpenMastery?: (concept: string) => void;
}) {
  const steps = session.plan ?? [];
  const done = session.step_results ?? [];
  const titles: Record<string, string> = {};
  for (const result of done) titles[result.step_id] = result.step_id;

  return (
    <div className="flex flex-col gap-4 h-full overflow-auto p-4">
      <section>
        <h3 className="text-[11px] uppercase tracking-wide muted mb-2.5">学习路径</h3>
        <ol className="flex flex-col gap-0.5">
          <PathRow
            label="前测诊断"
            state={session.probe_score !== undefined && steps.length ? "done" : "current"}
            detail={steps.length ? `${Math.round(session.probe_score * 100)}%` : undefined}
          />
          {steps.map((stepId, index) => {
            const result = done.find((r) => r.step_id === stepId);
            const isCurrent = index === session.step_index && session.phase !== "done";
            return (
              <PathRow
                key={stepId}
                label={session.current_step?.id === stepId ? session.current_step.title : stepId}
                state={result ? (result.correct ? "done" : "partial") : isCurrent ? "current" : "todo"}
                detail={
                  result
                    ? result.correct
                      ? `${result.attempts} 次`
                      : result.resolved === "revealed"
                        ? "已复盘"
                        : "未通过"
                    : undefined
                }
              />
            );
          })}
          <PathRow
            label="后测验证"
            state={
              session.phase === "done"
                ? "done"
                : session.phase === "verify" || session.phase === "report"
                  ? "current"
                  : "todo"
            }
            detail={
              session.phase === "done" ? `${Math.round(session.verify_score * 100)}%` : undefined
            }
          />
        </ol>
        <p className="text-[11px] muted mt-2.5">
          当前阶段：{PHASE_LABEL[session.phase] ?? session.phase}
        </p>
      </section>

      <section>
        <h3 className="text-[11px] uppercase tracking-wide muted mb-2.5">掌握度</h3>
        <div className="flex flex-col gap-2.5">
          {(session.mission.concepts ?? []).map((concept) => {
            const after = session.mastery?.[concept] ?? 0.35;
            const before = session.mastery_before?.[concept] ?? after;
            const delta = after - before;
            return (
              <button
                key={concept}
                onClick={() => onOpenMastery?.(concept)}
                className="text-left group"
                title="点击查看这个分数是根据什么给出的"
              >
                <div className="flex items-baseline justify-between mb-1">
                  <span className="mono text-[10.5px] truncate pr-2 group-hover:opacity-80">
                    {concept}
                  </span>
                  <span className="mono text-[10.5px] shrink-0">
                    {Math.round(after * 100)}%
                    {Math.abs(delta) >= 0.01 && (
                      <span
                        style={{
                          color: delta > 0 ? "var(--color-ok-500)" : "var(--color-bad-500)",
                        }}
                      >
                        {" "}
                        {delta > 0 ? "↑" : "↓"}
                        {Math.abs(Math.round(delta * 100))}
                      </span>
                    )}
                  </span>
                </div>
                <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "var(--panel-2)" }}>
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${Math.max(2, after * 100)}%`,
                      background:
                        after >= 0.7
                          ? "var(--color-ok-500)"
                          : after >= 0.45
                            ? "var(--color-warn-500)"
                            : "var(--color-bad-500)",
                      transition: "width .5s cubic-bezier(.22,1,.36,1)",
                    }}
                  />
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {session.misconceptions?.length > 0 && (
        <section>
          <h3 className="text-[11px] uppercase tracking-wide muted mb-2">已识别的误区</h3>
          <div className="flex flex-col gap-1">
            {session.misconceptions.map((tag) => (
              <span
                key={tag}
                className="mono text-[10.5px] px-2 py-1 rounded"
                style={{
                  background: "color-mix(in oklab, var(--color-bad-500) 10%, transparent)",
                  color: "var(--color-bad-500)",
                }}
              >
                {tag}
              </span>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function PathRow({
  label,
  state,
  detail,
}: {
  label: string;
  state: "done" | "current" | "todo" | "partial";
  detail?: string;
}) {
  const marks = { done: "✓", current: "●", partial: "◐", todo: "○" };
  const colors = {
    done: "var(--color-ok-500)",
    current: "var(--color-accent-500)",
    partial: "var(--color-warn-500)",
    todo: "var(--muted)",
  };
  return (
    <li className="flex items-center gap-2 py-1">
      <span className="text-[11px] w-3 shrink-0" style={{ color: colors[state] }}>
        {marks[state]}
      </span>
      <span
        className="text-[12.5px] flex-1 truncate"
        style={{
          color: state === "todo" ? "var(--muted)" : "var(--text)",
          fontWeight: state === "current" ? 600 : 400,
        }}
      >
        {label}
      </span>
      {detail && <span className="mono text-[10.5px] muted shrink-0">{detail}</span>}
    </li>
  );
}

export function MasteryEvidence({
  concept,
  changes,
  onClose,
}: {
  concept: string;
  changes: MasteryChange[];
  onClose: () => void;
}) {
  const relevant = changes.filter((c) => c.concept === concept);
  return (
    <div className="panel p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="mono text-[12px] font-semibold">{concept}</span>
        <button onClick={onClose} className="muted text-[15px] leading-none px-1">
          ×
        </button>
      </div>
      <p className="text-[11.5px] muted mb-2.5">这个分数是这样来的——每一次变化都记着依据：</p>
      {relevant.length === 0 && <p className="text-[12px] muted">本轮还没有更新过。</p>}
      <ol className="flex flex-col gap-2">
        {relevant.map((change, i) => (
          <li key={i} className="text-[12px] flex flex-col gap-0.5">
            <span className="mono">
              {Math.round(change.before * 100)}% → {Math.round(change.after * 100)}%
              <span
                style={{ color: change.delta > 0 ? "var(--color-ok-500)" : "var(--color-bad-500)" }}
              >
                {" "}
                ({change.delta > 0 ? "+" : ""}
                {Math.round(change.delta * 100)})
              </span>
            </span>
            <span className="muted">{change.reason}</span>
            {change.evidence_ids.length > 0 && (
              <span className="mono text-[10.5px] muted">
                依据 {change.evidence_ids.join("、")}
              </span>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
