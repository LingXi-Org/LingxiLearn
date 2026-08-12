"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AppWindow,
  ArrowLeft,
  BarChart3,
  BookOpen,
  CheckCircle2,
  CircleAlert,
  Download,
  FileQuestion,
  FlaskConical,
  Layers3,
  Monitor,
  Network,
  RefreshCw,
  RotateCcw,
  Home,
  MoreHorizontal,
  Sparkles,
} from "lucide-react";
import { CodeBlock } from "@/components/ai-elements/code-block";
import { AttachmentEmpty, Attachments } from "@/components/ai-elements/attachments";
import { Terminal } from "@/components/ai-elements/terminal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FrameInspector } from "@/components/viz/FrameInspector";
import { LatencyWaterfall } from "@/components/viz/LatencyWaterfall";
import { PacketLadder } from "@/components/viz/PacketLadder";
import { SimConsole } from "@/components/viz/SimConsole";
import type { ArtifactDescriptor } from "@/lib/workspace";
import { EMPTY_ATTRIBUTION } from "@/lib/workspace";
import type { Attribution, Evidence, Item, Report, RunEvent, SessionSnapshot } from "@/lib/types";
import { BUCKETS, ROLE_COLORS } from "@/lib/types";

const CAPABILITY = {
  course: { title: "自由 Prompt → 课程规划", description: "需要新的任务规划、课程内容与 Artifact 持久化接口。", icon: BookOpen },
  mistakes: { title: "错题上传与解析", description: "需要文件上传、OCR/文档解析和题目结构化接口。", icon: FileQuestion },
  interactive_task: { title: "交互式学习任务生成", description: "需要任务规划器和受控 Artifact schema，不能用假 HTML 代替。", icon: FlaskConical },
  general: { title: "通用学习任务", description: "需要自由任务 API 与可恢复的 Agent 执行流。", icon: Sparkles },
} as const;

export function ArtifactWorkspace({
  artifact,
  session,
  events = [],
  busy = false,
  submit,
  onBackToConversation,
}: {
  artifact: ArtifactDescriptor;
  session?: SessionSnapshot | null;
  events?: RunEvent[];
  busy?: boolean;
  submit?: (answer: unknown) => Promise<void>;
  onBackToConversation?: () => void;
}) {
  return (
    <section className="flex h-full min-h-0 flex-col bg-white" data-testid="artifact-workspace">
      <header className="flex h-[52px] shrink-0 items-center gap-3 border-b border-[#dedede] bg-white px-3 sm:px-4 lg:hidden">
        {onBackToConversation && (
          <button onClick={onBackToConversation} className="grid size-8 place-items-center rounded-lg hover:bg-white lg:hidden" aria-label="返回对话">
            <ArrowLeft className="size-4" />
          </button>
        )}
        <span className="grid size-8 place-items-center rounded-full border border-black/[.09] bg-white text-[var(--muted)]">
          <ArtifactIcon kind={artifact.kind} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h2 className="truncate rounded-full border border-[#d7d7d7] bg-[#f7f7f7] px-4 py-1.5 text-sm font-medium text-[#202020]">学习成果</h2>
            {artifact.source === "mock" && <Badge variant="secondary">Mock · Coming Soon</Badge>}
            {artifact.status === "running" && <Badge><span className="size-1.5 animate-pulse rounded-full bg-white" /> Live</Badge>}
          </div>
        </div>
        <div className="ml-auto flex items-center gap-1.5">
          <Button variant="outline" size="icon" disabled title="返回上一步"><RotateCcw className="size-4" /></Button>
          <Button variant="outline" size="icon" disabled title="刷新"><RefreshCw className="size-4" /></Button>
          <Button variant="outline" size="icon" disabled title="首页"><Home className="size-4" /></Button>
          <Button variant="outline" size="icon" disabled title="更多"><MoreHorizontal className="size-4" /></Button>
        </div>
      </header>

      <div className="artifact-stage min-h-0 flex-1 overflow-hidden border-t border-[#dedede] bg-[#fafafa]">
        {artifact.kind === "draft" && <DraftArtifact artifact={artifact} />}
        {artifact.kind === "empty" && <EmptyArtifact artifact={artifact} />}
        {artifact.kind === "assessment" && submit && <AssessmentArtifact key={artifact.id} title={artifact.title} items={artifact.items ?? []} kind={artifact.assessmentKind} busy={busy} submit={submit} />}
        {artifact.kind === "packet_lab" && <PacketLabArtifact artifact={artifact} />}
        {artifact.kind === "attribution" && submit && <AttributionArtifact artifact={artifact} events={events} busy={busy} submit={submit} />}
        {artifact.kind === "sim_console" && (
          <div className="h-full overflow-auto p-3 sm:p-5">
            <SimConsole scenario={artifact.scenario} seed={artifact.seed} submitting={busy} onSubmit={submit ? (actions) => submit({ actions }) : undefined} />
          </div>
        )}
        {artifact.kind === "report" && <LearningReportArtifact report={artifact.report} evidence={artifact.evidence} />}
      </div>

      {session?.pending?.value.kind === "answer" && session.pending.value.prompt?.expects === "choice" && submit && (
        <ChoiceDock
          choices={session.pending.value.prompt.choices ?? []}
          stepId={session.pending.value.step_id ?? "step"}
          busy={busy}
          submit={submit}
        />
      )}
    </section>
  );
}

function ArtifactIcon({ kind }: { kind: ArtifactDescriptor["kind"] }) {
  if (kind === "packet_lab") return <Network className="size-4" />;
  if (kind === "attribution" || kind === "report") return <BarChart3 className="size-4" />;
  if (kind === "sim_console") return <FlaskConical className="size-4" />;
  if (kind === "assessment") return <CheckCircle2 className="size-4" />;
  if (kind === "draft") return <Layers3 className="size-4" />;
  return <AppWindow className="size-4" />;
}

function EmptyArtifact({ artifact }: { artifact: Extract<ArtifactDescriptor, { kind: "empty" }> }) {
  return (
    <div className="grid h-full place-items-center p-8 text-center">
      <div>
        <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-white text-[var(--muted-2)] shadow-sm"><Monitor className="size-6" /></span>
        <h3 className="mt-4 text-sm font-semibold">等待新的 Artifact</h3>
        <p className="mt-2 max-w-sm text-xs leading-5 text-[var(--muted)]">{artifact.description}</p>
      </div>
    </div>
  );
}

function DraftArtifact({ artifact }: { artifact: Extract<ArtifactDescriptor, { kind: "draft" }> }) {
  const capability = CAPABILITY[artifact.capability];
  const Icon = capability.icon;
  return (
    <div className="h-full overflow-auto p-4 sm:p-8" data-testid="draft-artifact">
      <div className="mx-auto max-w-3xl">
        <Card className="overflow-hidden border-amber-200 bg-amber-50/70">
          <div className="flex items-start gap-4 p-5 sm:p-6">
            <span className="grid size-11 shrink-0 place-items-center rounded-2xl bg-white text-amber-700 shadow-sm"><Icon className="size-5" /></span>
            <div>
              <Badge variant="secondary">未执行 · Coming Soon</Badge>
              <h3 className="mt-3 text-lg font-semibold">{capability.title}</h3>
              <p className="mt-2 text-sm leading-6 text-amber-950/70">{capability.description}</p>
            </div>
          </div>
        </Card>

        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <Card className="p-5">
            <div className="text-xs font-semibold">你的任务草稿</div>
            <blockquote className="mt-3 border-l-2 border-[var(--brand)] pl-3 text-sm leading-6 text-[var(--muted)]">{artifact.prompt}</blockquote>
          </Card>
          <Card className="p-5">
            <div className="text-xs font-semibold">真实接入后才会发生</div>
            <ol className="mt-3 space-y-2 text-xs leading-5 text-[var(--muted)]">
              <li>1. 服务端创建可恢复的任务与 Thread</li>
              <li>2. SSE 推送计划、工具调用与 Artifact revision</li>
              <li>3. 所有产物带来源、状态和持久化标识</li>
            </ol>
          </Card>
        </div>

        <div className="mt-5 space-y-3">
          <Attachments variant="list"><AttachmentEmpty className="w-full rounded-lg border">尚未上传任何文件</AttachmentEmpty></Attachments>
          <CodeBlock language="typescript" code={'type ArtifactUpdate = {\n  taskId: string;\n  revision: number;\n  kind: "course" | "document" | "code" | "chart" | "file";\n  status: "running" | "ready" | "error";\n  payload: unknown;\n};'} />
          <Terminal output={'$ lingxi-agent run\nnot connected — no task API is available'} />
        </div>
      </div>
    </div>
  );
}

function AssessmentArtifact({
  title,
  items,
  kind,
  busy,
  submit,
}: {
  title: string;
  items: Item[];
  kind: "probe" | "verify";
  busy: boolean;
  submit: (answer: unknown) => Promise<void>;
}) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const complete = items.length > 0 && items.every((item) => answers[item.id]);
  return (
    <div className="h-full overflow-auto p-4 sm:p-8">
      <div className="mx-auto max-w-3xl">
        <Badge variant={kind === "probe" ? "default" : "secondary"}>{kind === "probe" ? "开始前诊断" : "学习结果验证"}</Badge>
        <h3 className="mt-3 text-xl font-semibold">{title}</h3>
        <p className="mt-2 text-xs leading-5 text-[var(--muted)]">结果由确定性规则判定，用来调整后续学习路径，不是考试成绩。</p>
        <div className="mt-6 space-y-4">
          {items.map((item, index) => (
            <Card key={item.id} className="p-4 sm:p-5" data-testid={`item-${item.id}`}>
              <div className="flex gap-3">
                <span className="font-mono text-[11px] text-[var(--muted-2)]">{String(index + 1).padStart(2, "0")}</span>
                <div className="flex-1">
                  <p className="text-sm font-medium leading-6">{item.prompt}</p>
                  <div className="mt-3 grid gap-2">
                    {item.choices.map((choice) => (
                      <button
                        key={choice.value}
                        data-testid={`item-${item.id}-${choice.value.toLowerCase()}`}
                        onClick={() => setAnswers((current) => ({ ...current, [item.id]: choice.value }))}
                        className="rounded-xl border px-3 py-2.5 text-left text-xs leading-5 transition-colors"
                        style={{ borderColor: answers[item.id] === choice.value ? "var(--brand)" : "var(--line)", background: answers[item.id] === choice.value ? "var(--brand-soft)" : "white" }}
                      >
                        <span className="mr-2 font-mono text-[10px] text-[var(--muted)]">{choice.value.toUpperCase()}</span>{choice.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
        <Button data-testid="submit-items" className="mt-5 w-full" disabled={!complete || busy} onClick={() => void submit({ answers })}>
          {busy ? "正在判定…" : kind === "probe" ? "提交并生成学习路径" : "提交学习验证"}
        </Button>
      </div>
    </div>
  );
}

function PacketLabArtifact({ artifact }: { artifact: Extract<ArtifactDescriptor, { kind: "packet_lab" }> }) {
  const [selected, setSelected] = useState<number>();
  return (
    <div className="grid h-full min-h-0 lg:grid-cols-[minmax(0,1fr)_300px]">
      <div className="min-h-0 overflow-hidden border-r border-[var(--line-soft)]">
        {artifact.ladder ? <PacketLadder data={artifact.ladder} roles={artifact.roles} selected={selected} onSelect={setSelected} /> : <FrameList frames={artifact.frames} roles={artifact.roles} selected={selected} onSelect={setSelected} />}
      </div>
      <div className="min-h-0 overflow-auto bg-white p-3">
        <FrameInspector frame={artifact.frames.find((frame) => frame.number === selected) ?? null} role={selected ? artifact.roles[String(selected)] : undefined} onClose={() => setSelected(undefined)} />
        {!selected && <p className="p-4 text-xs leading-5 text-[var(--muted)]">选择任意数据帧，查看逐字段解码和原始字节。</p>}
      </div>
    </div>
  );
}

function AttributionArtifact({
  artifact,
  events,
  busy,
  submit,
}: {
  artifact: Extract<ArtifactDescriptor, { kind: "attribution" }>;
  events: RunEvent[];
  busy: boolean;
  submit: (answer: unknown) => Promise<void>;
}) {
  const [value, setValue] = useState<Attribution>(EMPTY_ATTRIBUTION);
  const [activeBucket, setActiveBucket] = useState<string>(BUCKETS[0].id);
  const [selected, setSelected] = useState<number>();
  useEffect(() => setValue(EMPTY_ATTRIBUTION), [artifact.id]);
  const judgement = useMemo(() => [...events].reverse().find((event) => event.kind === "answer.judged")?.payload.judgement as Record<string, any> | undefined, [events]);
  const focus = value.pins[activeBucket] ?? [];
  const pin = (frame: number) => {
    setSelected(frame);
    setValue((current) => {
      const frames = current.pins[activeBucket] ?? [];
      return { ...current, pins: { ...current.pins, [activeBucket]: frames.includes(frame) ? frames.filter((item) => item !== frame) : [...frames, frame] } };
    });
  };
  return (
    <div className="grid h-full min-h-0 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="min-h-0 overflow-hidden border-r border-[var(--line-soft)]">
        {artifact.ladder ? <PacketLadder data={artifact.ladder} roles={artifact.roles} selected={selected} onSelect={pin} highlight={focus} /> : <FrameList frames={artifact.frames} roles={artifact.roles} selected={selected} onSelect={pin} />}
      </div>
      <div className="min-h-0 overflow-auto bg-white p-3">
        <LatencyWaterfall
          totalMs={artifact.waterfall?.total_ms ?? 0}
          value={value}
          onChange={setValue}
          activeBucket={activeBucket}
          onActiveBucket={setActiveBucket}
          truth={judgement?.detail?.buckets && artifact.waterfall ? { buckets: artifact.waterfall.buckets, detail: judgement.detail } : undefined}
        />
        <Button className="mt-3 w-full" disabled={busy} onClick={() => void submit(value)}>
          {busy ? "正在判定…" : "提交归因表"}
        </Button>
      </div>
    </div>
  );
}

function ChoiceDock({ choices, stepId, busy, submit }: { choices: { value: string; label: string }[]; stepId: string; busy: boolean; submit: (answer: unknown) => Promise<void> }) {
  const [choice, setChoice] = useState<string>();
  useEffect(() => setChoice(undefined), [stepId]);
  return (
    <div className="shrink-0 border-t border-[var(--line)] bg-white p-3" data-step={stepId}>
      <div className="mx-auto flex max-w-3xl flex-wrap gap-2">
        {choices.map((option) => (
          <button key={option.value} data-testid={`choice-${option.value}`} onClick={() => setChoice(option.value)} className="flex-1 rounded-xl border px-3 py-2 text-left text-xs" style={{ borderColor: choice === option.value ? "var(--brand)" : "var(--line)", background: choice === option.value ? "var(--brand-soft)" : "white" }}>
            <span className="mr-2 font-mono text-[10px] text-[var(--muted)]">{option.value.toUpperCase()}</span>{option.label}
          </button>
        ))}
        <Button data-testid="submit-choice" disabled={!choice || busy} onClick={() => choice && void submit({ choice })}>{busy ? "判定中" : "提交"}</Button>
      </div>
    </div>
  );
}

function FrameList({ frames, roles, selected, onSelect }: { frames: Extract<ArtifactDescriptor, { kind: "packet_lab" }>["frames"]; roles: Record<string, string>; selected?: number; onSelect: (frame: number) => void }) {
  if (!frames.length) return <div className="grid h-full place-items-center text-xs text-[var(--muted)]">正在解析抓包…</div>;
  return (
    <div className="h-full overflow-auto p-3">
      {frames.map((frame) => (
        <button key={frame.number} data-testid={`frame-label-${frame.number}`} onClick={() => onSelect(frame.number)} className="flex w-full gap-2 rounded-lg px-2 py-1.5 text-left font-mono text-[10.5px]" style={{ background: selected === frame.number ? "var(--surface-3)" : "transparent", color: ROLE_COLORS[roles[String(frame.number)]] ?? "var(--muted)" }}>
          <span className="w-8 text-[var(--muted-2)]">#{frame.number}</span><span className="w-16 text-[var(--muted-2)]">{frame.ts.toFixed(4)}</span><span className="truncate">{frame.summary}</span>
        </button>
      ))}
    </div>
  );
}

function LearningReportArtifact({ report, evidence }: { report: Report; evidence: Evidence[] }) {
  const gain = report.learning_gain ?? 0;
  return (
    <div className="h-full overflow-auto p-4 sm:p-8" data-testid="report-root">
      <div className="mx-auto max-w-4xl">
        <Badge variant="secondary">任务完成</Badge>
        <p className="mt-3 text-xs text-[var(--muted)]">{report.mission_title}</p>
        <h3 className="mt-1 text-2xl font-semibold tracking-tight">{report.headline}</h3>
        <div className="mt-6 grid grid-cols-3 gap-3">
          <ReportStat label="前测" value={`${Math.round(report.probe_score * 100)}%`} />
          <ReportStat label="后测" value={`${Math.round(report.verify_score * 100)}%`} />
          <ReportStat label="学习增益" value={`${gain > 0 ? "+" : ""}${Math.round(gain * 100)}%`} accent={gain > 0} />
        </div>
        <div className="mt-7 grid gap-5 lg:grid-cols-2">
          <ReportList title="已经掌握" items={report.strengths} tone="good" />
          <ReportList title="仍需加强" items={report.gaps} tone="warn" />
        </div>
        <Card className="mt-5 p-5">
          <h4 className="text-xs font-semibold">掌握度变化</h4>
          <div className="mt-4 space-y-3">
            {Object.keys(report.mastery_after ?? {}).sort().map((concept) => {
              const before = report.mastery_before?.[concept] ?? 0;
              const after = report.mastery_after[concept];
              return (
                <div key={concept}>
                  <div className="mb-1.5 flex justify-between font-mono text-[10px]"><span>{concept}</span><span className="text-[var(--muted)]">{Math.round(before * 100)}% → <b className="text-[var(--ink)]">{Math.round(after * 100)}%</b></span></div>
                  <div className="h-2 overflow-hidden rounded-full bg-[var(--surface-3)]"><div className="h-full rounded-full bg-[var(--brand)]" style={{ width: `${after * 100}%` }} /></div>
                </div>
              );
            })}
          </div>
        </Card>
        <Card className="mt-5 p-5">
          <h4 className="text-xs font-semibold">可回溯证据 · {evidence.length}</h4>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {evidence.slice(-8).map((item) => <div key={item.id} className="rounded-xl bg-[var(--surface-2)] p-3"><div className="font-mono text-[9px] text-[var(--muted-2)]">{item.id} · {item.source}</div><p className="mt-1 text-xs">{item.summary}</p></div>)}
          </div>
        </Card>
      </div>
    </div>
  );
}

function ReportStat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return <Card className="p-4 text-center"><span className="block text-[10px] text-[var(--muted)]">{label}</span><strong className="mt-1 block font-mono text-xl" style={{ color: accent ? "var(--brand)" : "var(--ink)" }}>{value}</strong></Card>;
}

function ReportList({ title, items, tone }: { title: string; items: string[]; tone: "good" | "warn" }) {
  return <Card className="p-5"><h4 className="flex items-center gap-2 text-xs font-semibold">{tone === "good" ? <CheckCircle2 className="size-4 text-emerald-600" /> : <CircleAlert className="size-4 text-amber-600" />}{title}</h4><ul className="mt-3 space-y-2 text-xs leading-5 text-[var(--muted)]">{items?.map((item) => <li key={item} className="flex gap-2"><span>·</span><span>{item}</span></li>)}</ul></Card>;
}
