"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SimAction, SimState } from "@/lib/types";

/**
 * The learner *is* the sender.
 *
 * Every button here is a decision a real sender makes, and the simulator
 * answers back within a tick. Nothing about this can be looked up: the right
 * move depends on the window, the in-flight segments and the last ACK, and the
 * network reacts to whatever you choose.
 *
 * Stepping happens server-side for responsiveness, but grading never trusts it
 * — the submitted action log is replayed from the seed when the step is
 * handed in.
 */
export function SimConsole({
  scenario,
  seed,
  onSubmit,
  submitting,
}: {
  scenario: string;
  seed: number;
  onSubmit?: (actions: { op: string; seq?: number }[]) => void;
  submitting?: boolean;
}) {
  const [state, setState] = useState<SimState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  const reset = useCallback(() => {
    api
      .simInit(scenario, seed)
      .then(setState)
      .catch((e) => setError(String(e.message ?? e)));
  }, [scenario, seed]);

  useEffect(reset, [reset]);

  async function act(action: SimAction) {
    if (!state || state.done || busy) return;
    setBusy(true);
    try {
      setState(await api.simStep(state, action));
    } catch (e: any) {
      setError(String(e.message ?? e));
    } finally {
      setBusy(false);
    }
  }

  if (error) {
    return (
      <div className="panel p-4 text-[13px]" style={{ borderColor: "var(--color-bad-500)" }}>
        仿真器不可用：{error}
      </div>
    );
  }
  if (!state) return <div className="panel p-6 text-[13px] muted">正在准备仿真…</div>;

  const outstanding = state.next_seq - state.base;
  const roomLeft = state.window_size - outstanding;
  const canSend = roomLeft > 0 && state.next_seq < state.total_segments && !state.done;
  const recovery = state.dup_ack_count >= 3 || state.timeout_pending;

  return (
    <div className="flex flex-col gap-3 h-full overflow-auto" data-sim-done={state.done ? "1" : "0"}>
      <div className="panel p-3.5">
        <div className="flex items-center justify-between mb-2.5">
          <span className="text-[12.5px] font-medium">{state.title}</span>
          <span className="mono text-[11px] muted">
            tick {state.tick} · 已送达 {state.receiver_expected}/{state.total_segments}
          </span>
        </div>
        <p className="text-[11.5px] muted mb-3">{state.brief}</p>
        <WindowStrip state={state} />
      </div>

      <SeqTimeChart state={state} />

      {/* controls */}
      <div className="panel p-3.5">
        <div className="flex flex-wrap gap-2">
          <Button testId="sim-send" onClick={() => act({ op: "send" })} disabled={!canSend || busy} primary>
            发送第 {state.next_seq} 段
          </Button>
          <Button
            testId="sim-retransmit"
            onClick={() => act({ op: "retransmit", seq: state.base })}
            disabled={state.base >= state.next_seq || busy || state.done}
            emphasis={recovery}
          >
            重传第 {state.base} 段
          </Button>
          <Button
            onClick={() => act({ op: "retransmit_all" })}
            disabled={state.base >= state.next_seq || busy || state.done}
          >
            重传整个窗口
          </Button>
          <Button testId="sim-wait" onClick={() => act({ op: "wait" })} disabled={busy || state.done}>
            等一拍
          </Button>
          <Button onClick={reset} disabled={busy}>
            重来
          </Button>
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-3 text-[11.5px] muted mono">
          <span>base={state.base}</span>
          <span>next={state.next_seq}</span>
          <span>窗口空位 {roomLeft}/{state.window_size}</span>
          {state.dup_ack_count > 0 && (
            <span style={{ color: "var(--color-retx-500)" }}>
              重复 ACK ×{state.dup_ack_count}
            </span>
          )}
          {state.timer.running && (
            <span>定时器 → tick {state.timer.expires_at}</span>
          )}
          {state.timeout_pending && (
            <span style={{ color: "var(--color-retx-500)" }}>超时未处理</span>
          )}
        </div>
      </div>

      <EventLog events={state.events} />

      {onSubmit && (
        <button
          data-testid="sim-submit"
          onClick={() => onSubmit(state.actions.map(({ op, seq }) => (seq === undefined ? { op } : { op, seq })))}
          disabled={submitting || state.actions.length === 0}
          className="h-10 rounded-[10px] text-white font-medium text-[13.5px] disabled:opacity-60 shrink-0"
          style={{ background: state.done ? "var(--color-accent-500)" : "var(--color-ink-500)" }}
        >
          {submitting
            ? "正在判定…"
            : state.done
              ? `提交这 ${state.actions.length} 步操作`
              : `还没送完，仍要提交？（${state.actions.length} 步）`}
        </button>
      )}
    </div>
  );
}

function Button({
  children,
  onClick,
  disabled,
  primary,
  emphasis,
  testId,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  primary?: boolean;
  emphasis?: boolean;
  testId?: string;
}) {
  return (
    <button
      data-testid={testId}
      onClick={onClick}
      disabled={disabled}
      className={`h-8 px-3 rounded-[8px] text-[12.5px] font-medium border transition-all disabled:opacity-40 ${emphasis ? "pulse-ring" : ""}`}
      style={{
        background: primary ? "var(--color-accent-500)" : "var(--panel-2)",
        color: primary ? "#fff" : "var(--text)",
        borderColor: emphasis ? "var(--color-retx-500)" : "transparent",
      }}
    >
      {children}
    </button>
  );
}

/** Sender window: acknowledged · in flight · free · not yet sent. */
function WindowStrip({ state }: { state: SimState }) {
  const segments = Array.from({ length: state.total_segments }, (_, i) => i);
  const inflight = new Set(state.inflight.filter((p) => p.kind === "data").map((p) => p.seq));
  return (
    <div className="flex gap-1">
      {segments.map((seq) => {
        const acked = seq < state.base;
        const sent = seq < state.next_seq;
        const inWindow = seq >= state.base && seq < state.base + state.window_size;
        const buffered = state.receiver_buffer.includes(seq);
        let background = "var(--panel-2)";
        let color = "var(--muted)";
        if (acked) {
          background = "color-mix(in oklab, var(--color-ok-500) 22%, transparent)";
          color = "var(--color-ok-500)";
        } else if (inflight.has(seq)) {
          background = "color-mix(in oklab, var(--color-ttfb-500) 26%, transparent)";
          color = "var(--color-ttfb-500)";
        } else if (buffered) {
          background = "color-mix(in oklab, var(--color-connect-500) 22%, transparent)";
          color = "var(--color-connect-500)";
        } else if (sent) {
          background = "color-mix(in oklab, var(--color-retx-500) 20%, transparent)";
          color = "var(--color-retx-500)";
        }
        return (
          <div
            key={seq}
            title={`第 ${seq} 段${acked ? "：已确认" : buffered ? "：接收方已缓存" : inflight.has(seq) ? "：在途" : sent ? "：已发出，未确认" : ""}`}
            className="flex-1 h-8 rounded-[6px] grid place-items-center mono text-[11px] transition-colors"
            style={{
              background,
              color,
              outline: inWindow ? "1.5px solid var(--color-accent-500)" : "none",
              outlineOffset: "-1.5px",
            }}
          >
            {seq}
          </div>
        );
      })}
    </div>
  );
}

/** Sequence number against time — the classic plot, drawn from real events. */
function SeqTimeChart({ state }: { state: SimState }) {
  const sends = state.events.filter((e) => e.kind === "send" || e.kind === "retransmit");
  const acks = state.events.filter((e) => e.kind === "ack");
  const losses = state.events.filter((e) => e.kind === "lost");
  const maxTick = Math.max(state.tick, 12);
  const maxSeq = state.total_segments;

  const x = (tick: number) => 6 + (tick / maxTick) * 92;
  const y = (seq: number) => 92 - (seq / maxSeq) * 84;

  return (
    <div className="panel p-3.5">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[12.5px] font-medium">序号 — 时间</span>
        <div className="flex gap-3 text-[10.5px] muted">
          <Legend color="var(--color-accent-500)" label="发送" />
          <Legend color="var(--color-ok-500)" label="确认" />
          <Legend color="var(--color-retx-500)" label="丢失" />
        </div>
      </div>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="w-full h-[150px]">
        <line x1="6" y1="92" x2="98" y2="92" stroke="var(--line)" strokeWidth="0.4" />
        <line x1="6" y1="8" x2="6" y2="92" stroke="var(--line)" strokeWidth="0.4" />
        {acks.length > 1 && (
          <polyline
            points={acks.map((e) => `${x(e.tick)},${y(e.ack)}`).join(" ")}
            fill="none"
            stroke="var(--color-ok-500)"
            strokeWidth="0.6"
            vectorEffect="non-scaling-stroke"
          />
        )}
        {sends.map((e, i) => (
          <rect
            key={`s${i}`}
            x={x(e.tick) - 0.7}
            y={y(e.seq) - 2}
            width="1.4"
            height="4"
            rx="0.5"
            fill={e.kind === "retransmit" ? "var(--color-retx-500)" : "var(--color-accent-500)"}
          />
        ))}
        {losses.map((e, i) => (
          <g key={`l${i}`} stroke="var(--color-retx-500)" strokeWidth="0.5">
            <line x1={x(e.tick) - 1.2} y1={y(e.seq) - 2} x2={x(e.tick) + 1.2} y2={y(e.seq) + 2} />
            <line x1={x(e.tick) - 1.2} y1={y(e.seq) + 2} x2={x(e.tick) + 1.2} y2={y(e.seq) - 2} />
          </g>
        ))}
      </svg>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className="w-2 h-2 rounded-sm" style={{ background: color }} />
      {label}
    </span>
  );
}

const EVENT_LABEL: Record<string, string> = {
  send: "发送",
  retransmit: "重传",
  lost: "在网络中丢失",
  deliver: "接收方交付",
  buffer: "接收方缓存（失序）",
  ack: "累计确认",
  dup_ack: "重复确认",
  timeout: "定时器超时",
  wait: "等待",
  rejected: "无效操作",
  complete: "全部送达",
  duplicate_data: "重复数据（丢弃）",
  aborted: "已中止",
};

function EventLog({ events }: { events: SimState["events"] }) {
  const recent = events.slice(-14).reverse();
  return (
    <div className="panel p-3.5">
      <span className="text-[12.5px] font-medium">仿真日志</span>
      <div className="mt-2 flex flex-col gap-0.5 max-h-40 overflow-auto">
        {recent.length === 0 && <span className="text-[11.5px] muted">还没有动作。</span>}
        {recent.map((event, i) => (
          <div key={i} className="mono text-[11px] flex gap-2">
            <span className="muted shrink-0">t{String(event.tick).padStart(2, "0")}</span>
            <span
              style={{
                color:
                  event.kind === "lost" || event.kind === "timeout" || event.kind === "rejected"
                    ? "var(--color-retx-500)"
                    : event.kind === "deliver" || event.kind === "complete"
                      ? "var(--color-ok-500)"
                      : "var(--muted)",
              }}
            >
              {EVENT_LABEL[event.kind] ?? event.kind}
              {event.seq !== undefined && ` #${event.seq}`}
              {event.ack !== undefined && ` → ${event.ack}`}
              {event.reason ? `（${event.reason}）` : ""}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
