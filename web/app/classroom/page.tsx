"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api, subscribeEvents } from "@/lib/api";
import type {
  Attribution,
  Evidence,
  Frame,
  LadderData,
  RunEvent,
  SessionSnapshot,
  Waterfall,
} from "@/lib/types";
import { BUCKETS, ROLE_COLORS } from "@/lib/types";
import { Brand, BrainBadge, Pill, Spinner } from "@/components/Chrome";
import { PacketLadder } from "@/components/viz/PacketLadder";
import { LatencyWaterfall } from "@/components/viz/LatencyWaterfall";
import { FrameInspector } from "@/components/viz/FrameInspector";
import { SimConsole } from "@/components/viz/SimConsole";
import { LearningPath, MasteryEvidence } from "@/components/classroom/LearningPath";
import { CoachPanel } from "@/components/classroom/CoachPanel";
import { ProbeCard } from "@/components/classroom/ProbeCard";
import { EvidencePanel, RunTrace } from "@/components/classroom/RunTrace";

const EMPTY_ATTRIBUTION: Attribution = {
  allocations: Object.fromEntries(BUCKETS.map((b) => [b.id, 0])),
  pins: Object.fromEntries(BUCKETS.map((b) => [b.id, [] as number[]])),
};

export default function ClassroomPage() {
  return (
    <Suspense fallback={<div className="h-screen grid place-items-center"><Spinner label="加载中…" /></div>}>
      <Classroom />
    </Suspense>
  );
}

function Classroom() {
  const router = useRouter();
  const sessionId = useSearchParams().get("id") ?? "";

  const [session, setSession] = useState<SessionSnapshot | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  const [selectedFrame, setSelectedFrame] = useState<number>();
  const [attribution, setAttribution] = useState<Attribution>(EMPTY_ATTRIBUTION);
  const [activeBucket, setActiveBucket] = useState<string>(BUCKETS[0].id);
  const [sidePanel, setSidePanel] = useState<"evidence" | "trace">("evidence");
  const [masteryConcept, setMasteryConcept] = useState<string>();
  const [choice, setChoice] = useState<string>();

  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refresh = useCallback(async () => {
    if (!sessionId) return;
    try {
      const next = await api.session(sessionId);
      setSession(next);
      setBusy(next.status === "running");
      if (next.status !== "running") setChoice(undefined);
    } catch (e: any) {
      setError(String(e.message ?? e));
    }
  }, [sessionId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Safety net: the stream is the fast path, but a run that emits nothing for a
  // while must never leave the UI stuck on a spinner.
  useEffect(() => {
    if (session?.status !== "running") return;
    const timer = setInterval(refresh, 1500);
    return () => clearInterval(timer);
  }, [session?.status, refresh]);

  // The stream tells us *when* something changed; the snapshot is the source of
  // truth for *what* it is. Refreshes are debounced so a burst of tool events
  // costs one fetch, not eight.
  useEffect(() => {
    if (!sessionId) return;
    return subscribeEvents(
      sessionId,
      (event) => {
        setEvents((prev) => (prev.some((e) => e.sequence === event.sequence) ? prev : [...prev, event]));
        if (refreshTimer.current) clearTimeout(refreshTimer.current);
        refreshTimer.current = setTimeout(refresh, 180);
      },
      { onEnd: () => void refresh() },
    );
  }, [sessionId, refresh]);

  const pending = session?.pending?.value;
  const scene = pending?.stage?.scene ?? session?.stage?.scene ?? "probe";
  const props = (session?.stage?.props ?? {}) as Record<string, any>;

  const ladder = props.ladder as LadderData | undefined;
  const waterfall = props.waterfall as Waterfall | undefined;
  const frames = (props.frames as Frame[] | undefined) ?? [];
  const roles = waterfall?.frame_roles ?? {};

  const lastJudgement = useMemo(() => {
    const judged = [...events].reverse().find((e) => e.kind === "answer.judged");
    return judged?.payload?.judgement as Record<string, any> | undefined;
  }, [events]);

  // Highlight only what the learner themselves pinned — never the frames the
  // grader expects, which would hand over the answer through the UI.
  const focusFrames = useMemo(
    () => attribution.pins[activeBucket] ?? [],
    [attribution, activeBucket],
  );

  async function submit(answer: unknown) {
    if (!sessionId) return;
    setBusy(true);
    try {
      await api.answer(sessionId, answer);
      setTimeout(refresh, 250);
    } catch (e: any) {
      setError(String(e.message ?? e));
      setBusy(false);
    }
  }

  function pinFrame(frame: number) {
    setSelectedFrame(frame);
    if (scene !== "attribution" || !activeBucket) return;
    setAttribution((prev: Attribution) => {
      const current = prev.pins[activeBucket] ?? [];
      return {
        ...prev,
        pins: {
          ...prev.pins,
          [activeBucket]: current.includes(frame)
            ? current.filter((f: number) => f !== frame)
            : [...current, frame],
        },
      };
    });
  }

  if (!sessionId) {
    return (
      <Centered>
        <p className="text-[14px]">缺少会话 ID。</p>
        <Link href="/" className="text-[13px] underline underline-offset-4">
          返回首页
        </Link>
      </Centered>
    );
  }

  if (error && !session) {
    return (
      <Centered>
        <p className="text-[14px]" style={{ color: "var(--color-bad-500)" }}>
          {error}
        </p>
        <Link href="/" className="text-[13px] underline underline-offset-4">
          返回首页
        </Link>
      </Centered>
    );
  }

  if (!session) {
    return (
      <Centered>
        <Spinner label="正在载入会话…" />
      </Centered>
    );
  }

  if (session.phase === "done" && session.report && "headline" in session.report) {
    router.push(`/report/?id=${sessionId}`);
  }

  const totalMs = waterfall?.total_ms ?? 0;

  return (
    <div className="h-screen flex flex-col">
      <header
        className="h-14 px-4 sm:px-6 flex items-center gap-3 border-b shrink-0"
        style={{ borderColor: "var(--line)" }}
      >
        <Brand compact />
        <div className="h-5 w-px" style={{ background: "var(--line)" }} />
        <div className="min-w-0">
          <span className="text-[13.5px] font-medium block truncate">{session.mission.title}</span>
          <span className="text-[11px] muted block truncate">{session.mission.subtitle}</span>
        </div>
        <div className="ml-auto flex items-center gap-2.5">
          {session.status === "failed" && <Pill tone="bad">运行失败</Pill>}
          {busy && <Spinner />}
          <BrainBadge brain={session.brain} />
        </div>
      </header>

      {session.error && (
        <div
          className="px-6 py-2 text-[12.5px] shrink-0"
          style={{ background: "color-mix(in oklab, var(--color-bad-500) 12%, transparent)" }}
        >
          {session.error}
        </div>
      )}

      <div className="flex-1 grid min-h-0" style={{ gridTemplateColumns: "232px 1fr 330px" }}>
        {/* left */}
        <aside className="border-r min-h-0 overflow-hidden" style={{ borderColor: "var(--line)" }}>
          <LearningPath session={session} onOpenMastery={setMasteryConcept} />
        </aside>

        {/* centre */}
        <main className="min-h-0 overflow-hidden flex flex-col">
          {masteryConcept && (
            <div className="p-4 pb-0">
              <MasteryEvidence
                concept={masteryConcept}
                changes={session.mastery_changes ?? []}
                onClose={() => setMasteryConcept(undefined)}
              />
            </div>
          )}

          {(pending?.kind === "probe" || pending?.kind === "verify") && (
            <div className="flex-1 overflow-auto">
              <ProbeCard
                title={pending.title ?? ""}
                items={pending.items ?? []}
                kind={pending.kind}
                busy={busy}
                onSubmit={submit}
              />
            </div>
          )}

          {pending?.kind === "answer" && scene === "attribution" && (
            <div className="flex-1 grid min-h-0" style={{ gridTemplateColumns: "1fr 300px" }}>
              <div className="min-h-0 overflow-hidden border-r" style={{ borderColor: "var(--line)" }}>
                {ladder ? (
                  <PacketLadder
                    data={ladder}
                    roles={roles}
                    selected={selectedFrame}
                    onSelect={pinFrame}
                    highlight={focusFrames}
                  />
                ) : (
                  <FrameList
                    frames={frames}
                    roles={roles}
                    selected={selectedFrame}
                    onSelect={pinFrame}
                  />
                )}
              </div>
              <div className="min-h-0 overflow-auto p-3">
                <LatencyWaterfall
                  totalMs={totalMs}
                  value={attribution}
                  onChange={setAttribution}
                  activeBucket={activeBucket}
                  onActiveBucket={setActiveBucket}
                  truth={
                    lastJudgement?.detail?.buckets && waterfall
                      ? { buckets: waterfall.buckets, detail: lastJudgement.detail }
                      : undefined
                  }
                />
                <button
                  onClick={() => submit(attribution)}
                  disabled={busy}
                  className="w-full h-10 mt-3 rounded-[10px] text-white font-medium text-[13.5px] disabled:opacity-60"
                  style={{ background: "var(--color-accent-500)" }}
                >
                  {busy ? "正在判定…" : "提交归因表"}
                </button>
              </div>
            </div>
          )}

          {pending?.kind === "answer" && scene === "packet_lab" && (
            <div className="flex-1 grid min-h-0" style={{ gridTemplateColumns: "1fr 300px" }}>
              <div className="min-h-0 overflow-hidden border-r" style={{ borderColor: "var(--line)" }}>
                {ladder ? (
                  <PacketLadder
                    data={ladder}
                    roles={roles}
                    selected={selectedFrame}
                    onSelect={setSelectedFrame}
                  />
                ) : (
                  <FrameList
                    frames={frames}
                    roles={roles}
                    selected={selectedFrame}
                    onSelect={setSelectedFrame}
                  />
                )}
              </div>
              <div className="min-h-0 overflow-auto p-3">
                <FrameInspector
                  frame={frames.find((f) => f.number === selectedFrame) ?? null}
                  role={selectedFrame ? roles[String(selectedFrame)] : undefined}
                  onClose={() => setSelectedFrame(undefined)}
                />
                {!selectedFrame && (
                  <p className="text-[12px] muted p-3">
                    点时空图里的任意一帧，可以看到它逐字段的解码结果和原始字节。
                  </p>
                )}
              </div>
            </div>
          )}

          {pending?.kind === "answer" && scene === "sim_console" && (
            <div className="flex-1 min-h-0 overflow-auto p-4">
              {pending.prompt?.expects === "sim_action" ? (
                <SimConsole
                  scenario={String(props.scenario ?? "single-loss")}
                  seed={Number(props.seed ?? 7)}
                  submitting={busy}
                  onSubmit={(actions) => submit({ actions })}
                />
              ) : (
                <SimConsole
                  scenario={String(props.scenario ?? "single-loss")}
                  seed={Number(props.seed ?? 7)}
                />
              )}
            </div>
          )}

          {!pending && (
            <div className="flex-1 grid place-items-center">
              <Spinner label="教练正在准备下一步…" />
            </div>
          )}

          {/* choice answer bar */}
          {pending?.kind === "answer" && pending.prompt?.expects === "choice" && (
            <div
              className="border-t p-4 shrink-0"
              data-step={pending.step_id}
              style={{ borderColor: "var(--line)" }}
            >
              <div className="flex flex-col gap-1.5 max-w-3xl">
                {(pending.prompt.choices ?? []).map((option) => (
                  <button
                    key={option.value}
                    data-testid={`choice-${option.value}`}
                    onClick={() => setChoice(option.value)}
                    className="flex items-start gap-2.5 text-left px-3 py-2 rounded-[9px] border transition-colors"
                    style={{
                      borderColor: choice === option.value ? "var(--color-accent-500)" : "var(--line)",
                      background:
                        choice === option.value
                          ? "color-mix(in oklab, var(--color-accent-500) 8%, transparent)"
                          : "transparent",
                    }}
                  >
                    <span className="mono text-[11px] mt-0.5 muted">{option.value.toUpperCase()}</span>
                    <span className="text-[13.5px]">{option.label}</span>
                  </button>
                ))}
                <button
                  data-testid="submit-choice"
                  onClick={() => choice && submit({ choice })}
                  disabled={!choice || busy}
                  className="h-10 mt-1.5 rounded-[10px] text-white font-medium text-[13.5px] disabled:opacity-50"
                  style={{ background: "var(--color-accent-500)" }}
                >
                  {busy ? "正在判定…" : "提交"}
                </button>
              </div>
            </div>
          )}
        </main>

        {/* right */}
        <aside className="border-l min-h-0 flex flex-col" style={{ borderColor: "var(--line)" }}>
          <div className="flex-1 min-h-0 overflow-hidden" style={{ flexBasis: "58%" }}>
            <CoachPanel
              session={session}
              busy={busy}
              onRequestHint={() => submit({ request_hint: true, text: "我需要提示" })}
              onRequestWalkthrough={() => submit({ request_walkthrough: true, text: "我想看复盘" })}
              onCite={(evidence) => {
                const frame = Number((evidence.locator as any)?.frame);
                if (!Number.isNaN(frame)) setSelectedFrame(frame);
                setSidePanel("evidence");
              }}
            />
          </div>

          <div className="border-t shrink-0" style={{ borderColor: "var(--line)", flexBasis: "42%", minHeight: 0 }}>
            <div className="flex border-b" style={{ borderColor: "var(--line)" }}>
              {(
                [
                  ["evidence", `证据 ${session.evidence?.length ?? 0}`],
                  ["trace", "运行轨迹"],
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setSidePanel(key)}
                  className="flex-1 h-9 text-[12px] font-medium transition-colors"
                  style={{
                    color: sidePanel === key ? "var(--text)" : "var(--muted)",
                    borderBottom:
                      sidePanel === key ? "2px solid var(--color-accent-500)" : "2px solid transparent",
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="h-[calc(100%-2.25rem)] min-h-0">
              {sidePanel === "evidence" ? (
                <EvidencePanel
                  evidence={session.evidence ?? []}
                  onSelect={(evidence) => {
                    const frame = Number((evidence.locator as any)?.frame);
                    if (!Number.isNaN(frame)) setSelectedFrame(frame);
                  }}
                />
              ) : (
                <RunTrace events={events} evidence={session.evidence ?? []} />
              )}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-screen grid place-items-center">
      <div className="flex flex-col items-center gap-3">{children}</div>
    </div>
  );
}

function FrameList({
  frames,
  roles,
  selected,
  onSelect,
}: {
  frames: Frame[];
  roles: Record<string, string>;
  selected?: number;
  onSelect: (frame: number) => void;
}) {
  if (!frames.length) {
    return (
      <div className="h-full grid place-items-center">
        <Spinner label="正在解析抓包…" />
      </div>
    );
  }
  return (
    <div className="h-full overflow-auto p-2">
      {frames.map((frame) => (
        <button
          key={frame.number}
          data-testid={`frame-label-${frame.number}`}
          onClick={() => onSelect(frame.number)}
          className="w-full text-left mono text-[11.5px] px-2 py-1 rounded flex gap-2.5"
          style={{
            background: selected === frame.number ? "var(--panel-2)" : "transparent",
            color: ROLE_COLORS[roles[String(frame.number)]] ?? "var(--muted)",
          }}
        >
          <span className="muted w-8 shrink-0">#{frame.number}</span>
          <span className="muted w-16 shrink-0">{frame.ts.toFixed(4)}</span>
          <span className="truncate">{frame.summary}</span>
        </button>
      ))}
    </div>
  );
}
