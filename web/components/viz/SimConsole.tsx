"use client";

import { useCallback, useLayoutEffect, useRef, useState } from "react";
import { gsap } from "gsap";
import { api } from "@/lib/api";
import type { SimAction, SimState } from "@/lib/types";

const EVENT_LABEL: Record<string, string> = {
  send: "发送",
  retransmit: "重传",
  lost: "在网络中丢失",
  deliver: "接收方交付",
  buffer: "接收方缓存（失序）",
  ack: "累计确认",
  dup_ack: "重复确认",
  timeout: "定时器超时",
  wait: "等待一拍",
  rejected: "无效操作",
  complete: "全部送达",
  duplicate_data: "重复数据（丢弃）",
  aborted: "已中止",
};

/**
 * The learner is the sender. All visual state comes from the server-side
 * simulator, so the panel is a faithful view of the same state machine used
 * for replay and grading.
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
  const surfaceRef = useRef<HTMLDivElement>(null);

  const reset = useCallback(() => {
    setError(undefined);
    api
      .simInit(scenario, seed)
      .then(setState)
      .catch((e) => setError(String(e.message ?? e)));
  }, [scenario, seed]);

  useLayoutEffect(() => {
    if (!surfaceRef.current) return;
    const targets = surfaceRef.current.querySelectorAll<HTMLElement>("[data-sim-animate]");
    if (!targets.length) return;
    const ctx = gsap.context(() => {
      gsap.fromTo(
        targets,
        { opacity: 0.72, y: 5 },
        { opacity: 1, y: 0, duration: 0.34, stagger: 0.035, ease: "power2.out", overwrite: true },
      );
    }, surfaceRef);
    return () => ctx.revert();
  }, [state?.tick, state?.events.length]);

  useLayoutEffect(reset, [reset]);

  async function act(action: SimAction) {
    if (!state || state.done || busy) return;
    setBusy(true);
    setError(undefined);
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
        <div className="font-medium">仿真器不可用</div>
        <div className="mt-1 muted">{error}</div>
        <button className="mt-3 h-8 rounded-[8px] border px-3 text-[12px]" onClick={reset}>
          重新初始化
        </button>
      </div>
    );
  }
  if (!state) return <div className="panel p-6 text-[13px] muted">正在准备仿真…</div>;

  const outstanding = Math.max(0, state.next_seq - state.base);
  const roomLeft = Math.max(0, state.window_size - outstanding);
  const canSend = roomLeft > 0 && state.next_seq < state.total_segments && !state.done;
  const recovery = state.dup_ack_count >= 3 || state.timeout_pending;
  const progress = Math.round((state.receiver_expected / state.total_segments) * 100);
  const signal = state.done
    ? "全量交付"
    : state.timeout_pending
      ? "超时待处理"
      : state.dup_ack_count >= 3
        ? "重复 ACK"
        : outstanding === 0
          ? "窗口空闲"
          : "等待网络";

  return (
    <div ref={surfaceRef} className="flex h-full flex-col gap-3 overflow-auto pb-1" data-sim-done={state.done ? "1" : "0"}>
      <header className="panel overflow-hidden" data-sim-animate>
        <div className="border-b px-4 py-4" style={{ borderColor: "var(--line)" }}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="mb-2 flex items-center gap-2">
                <span className="rounded-full px-2 py-1 text-[10px] font-semibold tracking-[0.14em]" style={{ background: "color-mix(in oklab, var(--color-accent-500) 12%, transparent)", color: "var(--color-accent-600)" }}>
                  发送方控制台
                </span>
                <span className="mono text-[10px] muted">seed {state.seed}</span>
              </div>
              <h2 className="text-[18px] font-semibold tracking-[-0.02em]">{state.title}</h2>
              <p className="mt-1 max-w-[620px] text-[12px] leading-5 muted">{state.brief}</p>
            </div>
            <div className="flex items-center gap-2 rounded-[10px] px-3 py-2" style={{ background: "var(--panel-2)" }}>
              <span className="h-2 w-2 rounded-full" style={{ background: state.done ? "var(--color-ok-500)" : recovery ? "var(--color-retx-500)" : "var(--color-accent-500)" }} />
              <span className="text-[12px] font-medium">{signal}</span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-px sm:grid-cols-4" style={{ background: "var(--line)" }}>
          <Metric label="当前 tick" value={String(state.tick).padStart(2, "0")} detail="离散时间" />
          <Metric label="窗口占用" value={`${outstanding}/${state.window_size}`} detail={`${roomLeft} 个空位`} />
          <Metric label="累计确认" value={`${state.receiver_expected}/${state.total_segments}`} detail={`${progress}% 已交付`} />
          <Metric label="恢复信号" value={state.dup_ack_count ? `ACK ×${state.dup_ack_count}` : state.timeout_pending ? "TIMEOUT" : "—"} detail={state.timer.running ? `计时至 t${state.timer.expires_at}` : "无活动计时器"} alert={recovery} />
        </div>
      </header>

      <WindowLadder state={state} />
      <SeqTimeChart state={state} />

      <section className="panel p-4" data-sim-animate>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h3 className="text-[13px] font-semibold">下一步动作</h3>
            <p className="mt-1 text-[11px] leading-4 muted">每次操作推进一个 tick；网络结果会在服务端状态机中决定。</p>
          </div>
          <span className="mono text-[11px] muted">base={state.base} · next={state.next_seq}</span>
        </div>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
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
            testId="sim-retransmit-all"
            onClick={() => act({ op: "retransmit_all" })}
            disabled={state.base >= state.next_seq || busy || state.done}
          >
            重传整个窗口
          </Button>
          <Button testId="sim-wait" onClick={() => act({ op: "wait" })} disabled={busy || state.done}>
            等一拍
          </Button>
        </div>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t pt-3 text-[11px] muted" style={{ borderColor: "var(--line)" }}>
          <span>{state.actions.length} 步操作 · {state.inflight.filter((packet) => packet.kind === "data").length} 个数据包在途</span>
          <button className="rounded-[7px] px-2 py-1 transition-colors hover:bg-[var(--panel-2)]" onClick={reset} disabled={busy}>
            重置仿真
          </button>
        </div>
      </section>

      <EventLog events={state.events} />

      {onSubmit && (
        <div className="sticky bottom-0 z-10 rounded-[12px] border p-3 backdrop-blur" style={{ borderColor: "var(--line)", background: "color-mix(in oklab, var(--panel) 92%, transparent)" }} data-sim-animate>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-[12px] font-semibold">{state.done ? "仿真已完成" : "还可以继续探索"}</div>
              <div className="mt-1 text-[11px] muted">提交后将按 seed 重放 {state.actions.length} 步操作并判定。</div>
            </div>
            <button
              data-testid="sim-submit"
              onClick={() => onSubmit(state.actions.map(({ op, seq }) => (seq === undefined ? { op } : { op, seq })))}
              disabled={submitting || state.actions.length === 0}
              className="h-9 rounded-[9px] px-4 text-[12.5px] font-semibold text-white transition-opacity disabled:opacity-50"
              style={{ background: state.done ? "var(--color-accent-500)" : "var(--color-ink-500)" }}
            >
              {submitting ? "正在判定…" : state.done ? `提交这 ${state.actions.length} 步操作` : `提交当前进度（${state.actions.length} 步）`}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function Metric({ label, value, detail, alert }: { label: string; value: string; detail: string; alert?: boolean }) {
  return (
    <div className="min-w-0 bg-[var(--panel)] px-3 py-3">
      <div className="text-[10px] muted">{label}</div>
      <div className="mono mt-1 truncate text-[17px] font-semibold" style={{ color: alert ? "var(--color-retx-500)" : "var(--text)" }}>{value}</div>
      <div className="mt-1 truncate text-[10px] muted">{detail}</div>
    </div>
  );
}

/** Sender window and receiver state, derived from the simulator snapshot. */
function WindowLadder({ state }: { state: SimState }) {
  const dataInFlight = new Set(state.inflight.filter((packet) => packet.kind === "data").map((packet) => packet.seq));
  const windowEnd = Math.min(state.total_segments, state.base + state.window_size);
  const visibleSegments = Array.from({ length: state.total_segments }, (_, seq) => seq);

  return (
    <section className="panel p-4" data-sim-animate>
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h3 className="text-[13px] font-semibold">窗口协议现场</h3>
          <p className="mt-1 text-[11px] muted">蓝色边界是发送窗口；绿色是已累计确认，橙色表示仍在网络中。</p>
        </div>
        <div className="mono text-[11px] muted">窗口 [{state.base}, {windowEnd})</div>
      </div>

      <div className="mt-4 flex items-stretch gap-2 overflow-x-auto pb-1">
        <div className="flex w-[76px] shrink-0 flex-col justify-center rounded-[9px] border px-2 py-2" style={{ borderColor: "var(--line)", background: "var(--panel-2)" }}>
          <span className="text-[10px] muted">发送方</span>
          <span className="mt-1 text-[12px] font-semibold">base {state.base}</span>
          <span className="mono mt-1 text-[10px] muted">next {state.next_seq}</span>
        </div>
        <div className="flex min-w-[520px] flex-1 flex-col gap-2">
          <div className="flex items-center gap-1 px-1 text-[10px] muted">
            <span className="w-12 shrink-0">序号</span>
            {visibleSegments.map((seq) => <span key={seq} className="min-w-[34px] flex-1 text-center mono">{seq}</span>)}
          </div>
          <div className="flex items-center gap-1 rounded-[10px] border p-1" style={{ borderColor: "var(--line)" }}>
            <span className="w-12 shrink-0 px-1 text-[10px] muted">数据</span>
            {visibleSegments.map((seq) => {
              const acked = seq < state.base;
              const sent = seq < state.next_seq;
              const buffered = state.receiver_buffer.includes(seq);
              const inWindow = seq >= state.base && seq < windowEnd;
              const inFlight = dataInFlight.has(seq);
              const kind = acked ? "已确认" : buffered ? "接收方缓存" : inFlight ? "在途" : sent ? "未确认" : "可发送";
              return <div key={seq} title={`第 ${seq} 段：${kind}`} className="grid h-9 min-w-[34px] flex-1 place-items-center rounded-[6px] mono text-[10px] transition-colors" style={{ color: segmentColor({ acked, buffered, inFlight, sent }), background: segmentBackground({ acked, buffered, inFlight, sent }), outline: inWindow ? "1.5px solid var(--color-accent-500)" : "none", outlineOffset: "-1.5px" }}>{seq}</div>;
            })}
          </div>
          <div className="flex items-center gap-1 px-1">
            <span className="w-12 shrink-0 text-[10px] muted">接收</span>
            {visibleSegments.map((seq) => <div key={seq} className="min-w-[34px] flex-1 text-center text-[10px]" style={{ color: seq < state.receiver_expected ? "var(--color-ok-500)" : state.receiver_buffer.includes(seq) ? "var(--color-connect-500)" : "var(--muted-2)" }}>{seq < state.receiver_expected ? "交付" : state.receiver_buffer.includes(seq) ? "缓存" : "·"}</div>)}
          </div>
        </div>
        <div className="flex w-[76px] shrink-0 flex-col justify-center rounded-[9px] border px-2 py-2" style={{ borderColor: "var(--line)", background: "var(--panel-2)" }}>
          <span className="text-[10px] muted">接收方</span>
          <span className="mt-1 text-[12px] font-semibold">期望 {state.receiver_expected}</span>
          <span className="mt-1 text-[10px] muted">缓存 {state.receiver_buffer.length}</span>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[10px] muted">
        <Legend color="var(--color-ok-500)" label="已确认" />
        <Legend color="var(--color-ttfb-500)" label="在途" />
        <Legend color="var(--color-connect-500)" label="失序缓存" />
        <Legend color="var(--color-retx-500)" label="已发出未确认" />
        <Legend color="var(--muted-2)" label="可发送" />
      </div>
    </section>
  );
}

function segmentColor({ acked, buffered, inFlight, sent }: { acked: boolean; buffered: boolean; inFlight: boolean; sent: boolean }) {
  if (acked) return "var(--color-ok-500)";
  if (inFlight) return "var(--color-ttfb-500)";
  if (buffered) return "var(--color-connect-500)";
  if (sent) return "var(--color-retx-500)";
  return "var(--muted)";
}

function segmentBackground({ acked, buffered, inFlight, sent }: { acked: boolean; buffered: boolean; inFlight: boolean; sent: boolean }) {
  if (acked) return "color-mix(in oklab, var(--color-ok-500) 18%, transparent)";
  if (inFlight) return "color-mix(in oklab, var(--color-ttfb-500) 22%, transparent)";
  if (buffered) return "color-mix(in oklab, var(--color-connect-500) 18%, transparent)";
  if (sent) return "color-mix(in oklab, var(--color-retx-500) 16%, transparent)";
  return "var(--panel-2)";
}

/** Sequence number against time, drawn from the same server event log used by grading. */
function SeqTimeChart({ state }: { state: SimState }) {
  const sends = state.events.filter((event) => event.kind === "send" || event.kind === "retransmit");
  const acks = state.events.filter((event) => event.kind === "ack" && typeof event.ack === "number");
  const losses = state.events.filter((event) => event.kind === "lost");
  const maxTick = Math.max(state.tick, 12);
  const maxSeq = Math.max(state.total_segments - 1, 1);
  const x = (tick: number) => 8 + (tick / maxTick) * 88;
  const y = (seq: number) => 90 - (seq / maxSeq) * 76;
  const xTicks = Array.from({ length: 5 }, (_, index) => Math.round((maxTick * index) / 4));

  return (
    <section className="panel p-4" data-sim-animate>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-[13px] font-semibold">序号 — 时间</h3>
          <p className="mt-1 text-[11px] muted">上升的发送点进入网络；确认线回到接收方已经拿到的最高连续序号。</p>
        </div>
        <div className="flex gap-3 text-[10px] muted">
          <Legend color="var(--color-accent-500)" label="发送" />
          <Legend color="var(--color-ok-500)" label="确认" />
          <Legend color="var(--color-retx-500)" label="丢失 / 重传" />
        </div>
      </div>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="mt-3 h-[172px] w-full" role="img" aria-label="序号与时间关系图">
        <line x1="8" y1="90" x2="96" y2="90" stroke="var(--line)" strokeWidth="0.45" vectorEffect="non-scaling-stroke" />
        <line x1="8" y1="14" x2="8" y2="90" stroke="var(--line)" strokeWidth="0.45" vectorEffect="non-scaling-stroke" />
        {Array.from({ length: 4 }, (_, index) => {
          const yPos = 90 - ((index + 1) / 4) * 76;
          return <line key={index} x1="8" y1={yPos} x2="96" y2={yPos} stroke="var(--line)" strokeWidth="0.25" strokeDasharray="1.5 2" vectorEffect="non-scaling-stroke" />;
        })}
        {acks.length > 1 && <polyline points={acks.map((event) => `${x(event.tick)},${y(Number(event.ack))}`).join(" ")} fill="none" stroke="var(--color-ok-500)" strokeWidth="0.8" vectorEffect="non-scaling-stroke" />}
        {sends.map((event, index) => <rect key={`send-${index}`} x={x(event.tick) - 0.65} y={y(Number(event.seq)) - 2} width="1.3" height="4" rx="0.4" fill={event.kind === "retransmit" ? "var(--color-retx-500)" : "var(--color-accent-500)"} />)}
        {losses.map((event, index) => <g key={`loss-${index}`} stroke="var(--color-retx-500)" strokeWidth="0.7" vectorEffect="non-scaling-stroke"><line x1={x(event.tick) - 1.4} y1={y(Number(event.seq)) - 2.2} x2={x(event.tick) + 1.4} y2={y(Number(event.seq)) + 2.2} /><line x1={x(event.tick) - 1.4} y1={y(Number(event.seq)) + 2.2} x2={x(event.tick) + 1.4} y2={y(Number(event.seq)) - 2.2} /></g>)}
        {xTicks.map((tick) => <text key={tick} x={x(tick)} y="98" textAnchor="middle" fill="var(--muted)" fontSize="3.2">t{tick}</text>)}
        <text x="2" y="16" fill="var(--muted)" fontSize="3.2">序号</text>
        <text x="91" y="98" fill="var(--muted)" fontSize="3.2">时间</text>
      </svg>
    </section>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-sm" style={{ background: color }} />{label}</span>;
}

function EventLog({ events }: { events: SimState["events"] }) {
  const recent = events.slice(-16).reverse();
  return (
    <section className="panel p-4" data-sim-animate>
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-[13px] font-semibold">事件时间线</h3>
          <p className="mt-1 text-[11px] muted">从最新事件向前回看，定位一次丢失、确认或超时如何改变窗口。</p>
        </div>
        <span className="mono text-[10px] muted">{events.length} events</span>
      </div>
      <div className="mt-3 flex max-h-52 flex-col gap-1 overflow-auto pr-1">
        {recent.length === 0 && <span className="text-[11.5px] muted">还没有动作。</span>}
        {recent.map((event, index) => {
          const critical = event.kind === "lost" || event.kind === "timeout" || event.kind === "rejected";
          const positive = event.kind === "deliver" || event.kind === "complete" || event.kind === "ack";
          return (
            <div key={`${event.tick}-${event.kind}-${index}`} className="flex items-start gap-2 rounded-[7px] px-2 py-1.5 text-[11px]" style={{ background: index === 0 ? "var(--panel-2)" : "transparent" }}>
              <span className="mono w-7 shrink-0 text-[10px] muted">t{String(event.tick).padStart(2, "0")}</span>
              <span className="mt-[3px] h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: critical ? "var(--color-retx-500)" : positive ? "var(--color-ok-500)" : "var(--color-accent-500)" }} />
              <span style={{ color: critical ? "var(--color-retx-500)" : positive ? "var(--color-ok-500)" : "var(--text)" }}>
                {EVENT_LABEL[event.kind] ?? event.kind}
                {event.seq !== undefined && ` · #${event.seq}`}
                {event.ack !== undefined && ` · ACK ${event.ack}`}
                {event.reason ? ` · ${event.reason}` : ""}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function Button({ children, onClick, disabled, primary, emphasis, testId }: { children: React.ReactNode; onClick: () => void; disabled?: boolean; primary?: boolean; emphasis?: boolean; testId?: string }) {
  return (
    <button data-testid={testId} onClick={onClick} disabled={disabled} className={`h-9 rounded-[8px] border px-3 text-[12px] font-medium transition-all disabled:opacity-40 ${emphasis ? "pulse-ring" : ""}`} style={{ background: primary ? "var(--color-accent-500)" : "var(--panel-2)", color: primary ? "#fff" : "var(--text)", borderColor: emphasis ? "var(--color-retx-500)" : "transparent" }}>
      {children}
    </button>
  );
}
