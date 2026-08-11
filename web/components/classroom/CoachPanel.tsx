"use client";

import { useState } from "react";
import type { Evidence, SessionSnapshot } from "@/lib/types";
import { Pill, Spinner } from "@/components/Chrome";

const HINT_LABEL = ["还没给提示", "第一级提示", "第二级提示", "第三级提示"];

const INTENT_LABEL: Record<string, string> = {
  ask: "提问",
  hint: "提示",
  probe_back: "追问",
  confirm: "确认",
  reveal: "复盘",
  wrap: "小结",
};

/**
 * Right rail: the coach.
 *
 * Deliberately shows the move's *intent* and hint level, and offers
 * "为什么问这个？". The hint level is kernel state — the panel reports it, it
 * does not choose it — and the walkthrough button only appears once the learner
 * has earned it by trying, which is the visible face of "引导而不是代做".
 */
export function CoachPanel({
  session,
  busy,
  onRequestHint,
  onRequestWalkthrough,
  onCite,
}: {
  session: SessionSnapshot;
  busy: boolean;
  onRequestHint: () => void;
  onRequestWalkthrough: () => void;
  onCite?: (evidence: Evidence) => void;
}) {
  const [showWhy, setShowWhy] = useState(false);
  const pending = session.pending?.value;
  const move = pending?.prompt ?? session.move;
  const hintLevel = pending?.hint_level ?? session.hint_level ?? 0;
  const attempts = pending?.attempts ?? session.attempts ?? 0;
  const step = session.current_step ?? {};
  const revealAfter = Number(step.reveal_after ?? 3);
  const canAskWalkthrough = attempts >= revealAfter && !session.answer_unlocked;

  const cited = (move?.evidence_ids ?? [])
    .map((id) => session.evidence?.find((e) => e.id === id))
    .filter(Boolean) as Evidence[];

  return (
    <div className="flex flex-col h-full">
      <header
        className="px-4 py-3 border-b flex items-center gap-2 shrink-0"
        style={{ borderColor: "var(--line)" }}
      >
        <span
          className="grid place-items-center w-6 h-6 rounded-full text-[11px] text-white shrink-0"
          style={{ background: "var(--color-accent-500)" }}
        >
          灵
        </span>
        <span className="text-[13px] font-semibold flex-1">AI 教练</span>
        {move?.intent && <Pill tone={move.intent === "confirm" ? "ok" : "neutral"}>{INTENT_LABEL[move.intent] ?? move.intent}</Pill>}
      </header>

      <div className="flex-1 overflow-auto p-4 flex flex-col gap-3">
        {busy && <Spinner label="教练正在看你的作答…" />}

        {move?.say ? (
          <div className="rise">
            <p className="text-[14px] leading-[1.75] whitespace-pre-wrap">{move.say}</p>

            {move.rationale && (
              <div className="mt-2.5">
                <button
                  onClick={() => setShowWhy((v) => !v)}
                  className="text-[11.5px] underline decoration-dotted underline-offset-4 muted hover:opacity-80"
                >
                  为什么问这个？
                </button>
                {showWhy && (
                  <p
                    className="text-[12px] muted mt-1.5 p-2.5 rounded-[9px] leading-relaxed rise"
                    style={{ background: "var(--panel-2)" }}
                  >
                    {move.rationale}
                  </p>
                )}
              </div>
            )}
          </div>
        ) : (
          !busy && <p className="text-[13px] muted">等待教练的下一步…</p>
        )}

        {cited.length > 0 && (
          <section>
            <h4 className="text-[11px] uppercase tracking-wide muted mb-1.5">教练引用的依据</h4>
            <div className="flex flex-col gap-1">
              {cited.map((evidence) => (
                <button
                  key={evidence.id}
                  onClick={() => onCite?.(evidence)}
                  className="text-left panel px-2.5 py-1.5 hover:opacity-80 transition-opacity"
                >
                  <span className="mono text-[10px] muted">{evidence.id} · {evidence.source}</span>
                  <span className="block text-[12px] mt-0.5">{evidence.summary}</span>
                </button>
              ))}
            </div>
          </section>
        )}
      </div>

      <footer
        className="p-4 border-t flex flex-col gap-2 shrink-0"
        style={{ borderColor: "var(--line)" }}
      >
        <div className="flex items-center justify-between text-[11px] muted">
          <span>{HINT_LABEL[Math.min(hintLevel, 3)]}</span>
          <span>已尝试 {attempts} 次</span>
        </div>

        <div className="flex gap-2">
          <button
            onClick={onRequestHint}
            disabled={busy || !session.pending || pending?.kind !== "answer"}
            className="flex-1 h-9 rounded-[9px] text-[12.5px] font-medium border disabled:opacity-40"
            style={{ borderColor: "var(--line)" }}
          >
            我需要提示
          </button>
          <button
            onClick={onRequestWalkthrough}
            disabled={busy || !canAskWalkthrough}
            title={
              canAskWalkthrough
                ? "查看完整推理"
                : `再试 ${Math.max(0, revealAfter - attempts)} 次之后可以要求复盘`
            }
            className="flex-1 h-9 rounded-[9px] text-[12.5px] font-medium border disabled:opacity-40"
            style={{ borderColor: "var(--line)" }}
          >
            给我复盘
          </button>
        </div>

        {!canAskWalkthrough && !session.answer_unlocked && (
          <p className="text-[11px] muted leading-relaxed">
            答案不会主动给出。先自己试 {revealAfter} 次，之后你可以要求完整复盘。
          </p>
        )}
      </footer>
    </div>
  );
}
