"use client";

import type { Evidence, RunEvent } from "@/lib/types";

const KIND_LABEL: Record<string, string> = {
  "run.started": "开始运行",
  "run.ended": "运行结束",
  "run.failed": "运行失败",
  "run.paused": "暂停等待",
  "node.started": "进入节点",
  "node.completed": "节点完成",
  "node.retrying": "节点重试",
  "interrupt.raised": "等待学生输入",
  "stage.changed": "切换舞台",
  "tool.started": "调用工具",
  "tool.completed": "工具返回",
  "evidence.added": "记录证据",
  "coach.move": "教练发问",
  "hint.escalated": "提升提示级别",
  "answer.judged": "判定作答",
  "mastery.updated": "更新掌握度",
  "probe.graded": "前测判分",
  "verify.graded": "后测判分",
  "step.completed": "完成步骤",
  "plan.ready": "生成学习路径",
  "report.ready": "生成报告",
};

const HIDDEN = new Set(["node.started", "node.completed", "run.started"]);

/**
 * The audit trail, shown to the learner rather than hidden in a debug console.
 *
 * Being able to see which node ran, which tool was called and what it returned
 * is what separates "the system says so" from "here is why". It is also the
 * fastest way for a teaching assistant to understand a student's session.
 */
export function RunTrace({
  events,
  evidence,
  onSelectEvidence,
  verbose = false,
}: {
  events: RunEvent[];
  evidence: Evidence[];
  onSelectEvidence?: (evidence: Evidence) => void;
  verbose?: boolean;
}) {
  const shown = verbose ? events : events.filter((e) => !HIDDEN.has(e.kind));

  return (
    <div className="flex flex-col gap-1.5 p-4 overflow-auto h-full">
      {shown.length === 0 && <p className="text-[12px] muted">还没有运行记录。</p>}
      {shown
        .slice()
        .reverse()
        .map((event) => {
          const evidenceId = event.payload?.evidence_id as string | undefined;
          const found = evidenceId ? evidence.find((e) => e.id === evidenceId) : undefined;
          return (
            <div key={event.sequence} className="flex items-start gap-2 text-[11.5px]">
              <span className="mono muted shrink-0 w-8 text-right">{event.sequence}</span>
              <span
                className="w-1.5 h-1.5 rounded-full mt-[5px] shrink-0"
                style={{ background: colorFor(event.kind) }}
              />
              <div className="flex-1 min-w-0">
                <span className="font-medium">{KIND_LABEL[event.kind] ?? event.kind}</span>
                {event.payload?.tool && (
                  <span className="mono muted"> · {String(event.payload.tool)}</span>
                )}
                {event.payload?.duration_ms !== undefined && (
                  <span className="mono muted"> {String(event.payload.duration_ms)}ms</span>
                )}
                {event.payload?.ok === false && (
                  <span style={{ color: "var(--color-bad-500)" }}> 失败</span>
                )}
                {event.payload?.level !== undefined && (
                  <span className="muted"> → 第 {String(event.payload.level)} 级</span>
                )}
                {found && onSelectEvidence && (
                  <button
                    onClick={() => onSelectEvidence(found)}
                    className="mono text-[10.5px] ml-1.5 underline decoration-dotted underline-offset-2"
                    style={{ color: "var(--color-accent-600)" }}
                  >
                    {found.id}
                  </button>
                )}
              </div>
            </div>
          );
        })}
    </div>
  );
}

function colorFor(kind: string): string {
  if (kind.startsWith("tool.")) return "var(--color-connect-500)";
  if (kind.startsWith("run.fail")) return "var(--color-bad-500)";
  if (kind === "evidence.added") return "var(--color-transfer-500)";
  if (kind === "coach.move" || kind === "hint.escalated") return "var(--color-accent-500)";
  if (kind === "answer.judged") return "var(--color-ttfb-500)";
  if (kind === "mastery.updated") return "var(--color-ok-500)";
  return "var(--color-ink-400)";
}

export function EvidencePanel({
  evidence,
  selected,
  onSelect,
}: {
  evidence: Evidence[];
  selected?: string;
  onSelect?: (evidence: Evidence) => void;
}) {
  const KIND_TEXT: Record<string, string> = {
    tool_result: "工具计算",
    knowledge: "资料引用",
    learner_action: "你的操作",
    simulation_frame: "仿真结果",
  };
  return (
    <div className="flex flex-col gap-1.5 p-4 overflow-auto h-full">
      <p className="text-[11.5px] muted mb-1">
        这一栏是本轮全部可回溯证据。教练的每一条技术结论都必须指向其中一条。
      </p>
      {evidence.map((item) => (
        <button
          key={item.id}
          onClick={() => onSelect?.(item)}
          className="text-left panel px-2.5 py-2 transition-colors"
          style={{
            borderColor: selected === item.id ? "var(--color-accent-500)" : "var(--line)",
          }}
        >
          <div className="flex items-center gap-1.5">
            <span className="mono text-[10px] muted">{item.id}</span>
            <span
              className="text-[9.5px] px-1 py-px rounded"
              style={{ background: "var(--panel-2)", color: "var(--muted)" }}
            >
              {KIND_TEXT[item.kind] ?? item.kind}
            </span>
          </div>
          <span className="block text-[12px] mt-0.5">{item.summary}</span>
          <span className="mono block text-[10px] muted mt-0.5 truncate">{item.source}</span>
        </button>
      ))}
    </div>
  );
}
