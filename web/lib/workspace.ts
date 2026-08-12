import type {
  Attribution,
  Evidence,
  Frame,
  LadderData,
  Report,
  RunEvent,
  SessionSnapshot,
  SimState,
  TranscriptRecord,
  Waterfall,
} from "@/lib/types";

export type WorkspaceMode =
  | { kind: "session"; sessionId: string }
  | { kind: "task"; taskId: string }
  | { kind: "draft"; prompt: string };

export interface WorkspaceMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
}

export type ActivityState = "pending" | "running" | "complete" | "error";

export interface ToolActivity {
  id: string;
  name: string;
  state: ActivityState;
  detail?: string;
}

export interface AgentActivity {
  plan: string[];
  activeStep: number | undefined;
  tools: ToolActivity[];
  evidence: Pick<Evidence, "id" | "summary" | "source">[];
  summary: string;
  running: boolean;
  error?: string;
}

interface ArtifactBase {
  id: string;
  title: string;
  source: "api" | "mock";
  status: "empty" | "running" | "ready" | "coming_soon" | "error";
  revision: number;
}

export type ArtifactDescriptor =
  | (ArtifactBase & { kind: "empty"; description: string })
  | (ArtifactBase & { kind: "draft"; prompt: string; capability: DraftCapability })
  | (ArtifactBase & {
      kind: "assessment";
      assessmentKind: "probe" | "verify";
      items: NonNullable<SessionSnapshot["pending"]>["value"]["items"];
    })
  | (ArtifactBase & {
      kind: "packet_lab";
      ladder?: LadderData;
      frames: Frame[];
      roles: Record<string, string>;
    })
  | (ArtifactBase & {
      kind: "attribution";
      ladder?: LadderData;
      waterfall?: Waterfall;
      frames: Frame[];
      roles: Record<string, string>;
    })
  | (ArtifactBase & { kind: "sim_console"; scenario: string; seed: number })
  | (ArtifactBase & { kind: "report"; report: Report; evidence: Evidence[] });

export type DraftCapability = "course" | "mistakes" | "interactive_task" | "general";

export function parseWorkspaceMode(params: URLSearchParams): WorkspaceMode | null {
  const sessionId = params.get("id")?.trim();
  if (sessionId) return { kind: "session", sessionId };
  const taskId = params.get("task")?.trim();
  if (taskId) return { kind: "task", taskId };
  if (params.get("draft") === "1") {
    return { kind: "draft", prompt: params.get("prompt")?.trim() || "新的学习任务" };
  }
  return null;
}

export function classifyDraft(prompt: string): DraftCapability {
  if (/错题|试卷|题目|拍照|上传/.test(prompt)) return "mistakes";
  if (/交互|实验|仿真|练习任务/.test(prompt)) return "interactive_task";
  if (/课程|课件|大纲|学习计划/.test(prompt)) return "course";
  return "general";
}

export function draftMessages(prompt: string): WorkspaceMessage[] {
  return [
    { id: "draft-user", role: "user", text: prompt },
    {
      id: "draft-boundary",
      role: "assistant",
      text: "这项需求已保存为本次页面中的任务草稿，但当前后端还没有自由 Prompt 规划与 Artifact 生成接口，因此我没有执行或生成结果。你可以在右侧查看真实的接入边界，或返回首页体验已经可用的网络课程任务。",
    },
  ];
}

export function transcriptToMessages(transcript: TranscriptRecord[]): WorkspaceMessage[] {
  return transcript.flatMap((record, index) => {
    if (record.role === "system") return [];
    const text = record.role === "coach" ? record.say : record.text;
    if (typeof text !== "string" || !text.trim()) return [];
    return [{
      id: `transcript-${index}-${record.role}`,
      role: record.role === "learner" ? "user" as const : "assistant" as const,
      text: text.trim(),
    }];
  });
}

export function reduceAgentActivity(events: RunEvent[], session?: SessionSnapshot | null): AgentActivity {
  const ordered = [...events].sort((a, b) => a.sequence - b.sequence);
  const toolMap = new Map<string, ToolActivity>();
  let plan = session?.plan ?? [];
  let error: string | undefined;

  for (const event of ordered) {
    if (event.kind === "plan.ready" && Array.isArray(event.payload.steps)) {
      plan = event.payload.steps.map(String);
    }
    if (event.kind === "tool.started") {
      const name = String(event.payload.tool ?? "tool");
      toolMap.set(name, { id: `${event.sequence}-${name}`, name, state: "running" });
    }
    if (event.kind === "tool.completed") {
      const name = String(event.payload.tool ?? "tool");
      const ok = event.payload.ok !== false;
      toolMap.set(name, {
        id: `${event.sequence}-${name}`,
        name,
        state: ok ? "complete" : "error",
        detail: ok
          ? event.payload.duration_ms !== undefined ? `完成 · ${String(event.payload.duration_ms)} ms` : "完成"
          : String(event.payload.error ?? "工具执行失败"),
      });
    }
    if (event.kind === "run.failed") error = String(event.payload.detail ?? "任务运行失败");
  }

  const running = session?.status === "running";
  const activeStep = session && plan.length && session.phase !== "done"
    ? Math.min(session.step_index ?? 0, plan.length - 1)
    : undefined;
  const phaseText: Record<string, string> = {
    intake: "正在读取任务上下文",
    diagnose: "正在诊断当前掌握情况",
    plan: "正在生成学习路径",
    investigate: "正在调用专业工具分析真实工件",
    coach: "正在整理下一步引导",
    await_learner: "等待你的输入",
    judge: "正在判定作答并更新证据",
    advance: "正在推进任务阶段",
    verify: "正在验证学习结果",
    report: "正在生成学习报告",
    done: "任务已完成",
  };

  return {
    plan,
    activeStep,
    tools: [...toolMap.values()],
    evidence: (session?.evidence ?? []).map(({ id, summary, source }) => ({ id, summary, source })),
    summary: error ?? phaseText[session?.phase ?? ""] ?? (running ? "Agent 正在处理任务" : "等待任务状态"),
    running,
    error,
  };
}

export function deriveArtifact(session: SessionSnapshot): ArtifactDescriptor {
  const report = session.report as Report;
  if (session.phase === "done" && report && typeof report.headline === "string") {
    return {
      id: `report-${session.id}`,
      kind: "report",
      title: "学习报告",
      source: "api",
      status: "ready",
      revision: session.step_results?.length ?? 1,
      report,
      evidence: session.evidence ?? [],
    };
  }

  const pending = session.pending?.value;
  if (pending?.kind === "probe" || pending?.kind === "verify") {
    return {
      id: `${pending.kind}-${session.id}-${session.step_index}`,
      kind: "assessment",
      title: pending.title || (pending.kind === "probe" ? "学习诊断" : "学习验证"),
      source: "api",
      status: "ready",
      revision: session.step_index,
      assessmentKind: pending.kind,
      items: pending.items ?? [],
    };
  }

  // The durable snapshot owns the complete artifact payload. Interrupts repeat
  // the scene/focus contract but may intentionally omit bulky props.
  const scene = pending?.stage?.scene ?? session.stage?.scene;
  const props = (session.stage?.props ?? pending?.stage?.props ?? {}) as Record<string, unknown>;
  const frames = (props.frames as Frame[] | undefined) ?? [];
  const waterfall = props.waterfall as Waterfall | undefined;
  const roles = waterfall?.frame_roles ?? {};
  const common = {
    id: `${scene ?? "empty"}-${session.step_index}`,
    source: "api" as const,
    status: session.status === "running" ? "running" as const : "ready" as const,
    revision: session.step_index,
  };

  if (scene === "packet_lab") {
    return { ...common, kind: "packet_lab", title: "数据包实验室", ladder: props.ladder as LadderData | undefined, frames, roles };
  }
  if (scene === "attribution") {
    return { ...common, kind: "attribution", title: "时延归因工作台", ladder: props.ladder as LadderData | undefined, waterfall, frames, roles };
  }
  if (scene === "sim_console") {
    return { ...common, kind: "sim_console", title: "可靠传输仿真实验", scenario: String(props.scenario ?? "single-loss"), seed: Number(props.seed ?? 7) };
  }
  return {
    ...common,
    kind: "empty",
    title: "App Viewer",
    status: session.status === "running" ? "running" : "empty",
    description: session.status === "running" ? "Agent 正在准备下一项学习工件。" : "当前阶段没有可展示的工件。",
  };
}

export function makeDraftArtifact(prompt: string): ArtifactDescriptor {
  return {
    id: "draft-artifact",
    kind: "draft",
    title: "任务草稿",
    source: "mock",
    status: "coming_soon",
    revision: 0,
    prompt,
    capability: classifyDraft(prompt),
  };
}

export const EMPTY_ATTRIBUTION: Attribution = {
  allocations: { dns: 0, tcp_connect: 0, ttfb: 0, transfer: 0, retransmission: 0 },
  pins: { dns: [], tcp_connect: [], ttfb: [], transfer: [], retransmission: [] },
};

export type FutureArtifactPayload =
  | { kind: "course"; modules: unknown[] }
  | { kind: "document"; content: string }
  | { kind: "code"; language: string; code: string }
  | { kind: "chart"; data: unknown[] }
  | { kind: "terminal"; lines: string[] }
  | { kind: "file"; name: string; url: string }
  | { kind: "sim-state"; state: SimState };
