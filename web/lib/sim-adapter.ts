import type {
  AgentTaskEvent,
  AgentTaskSnapshot,
  Evidence,
  RunEvent,
  SessionSnapshot,
  TranscriptRecord,
} from "@/lib/types";

/** The small client-side contract consumed by the Sim-derived chat surface. */
export type SimBlockType = "text" | "tool_call" | "subagent" | "status" | "resource";

export interface SimToolCall {
  id: string;
  name: string;
  status: "executing" | "success" | "error";
  displayTitle: string;
  detail?: string;
  agent?: string;
}

export interface SimContentBlock {
  type: SimBlockType;
  id: string;
  content?: string;
  toolCall?: SimToolCall;
  agent?: string;
  title?: string;
  status?: "running" | "complete" | "error";
}

export interface SimMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  contentBlocks: SimContentBlock[];
  status: "complete" | "streaming" | "error";
}

export interface SimActivity {
  summary: string;
  plan: string[];
  tools: SimToolCall[];
  evidence: Pick<Evidence, "id" | "summary" | "source">[];
  running: boolean;
  error?: string;
}

export interface SimResourceDescriptor {
  id: string;
  title: string;
  kind: "learning-artifact" | "background" | "visual";
  available: boolean;
  description: string;
}

function textForTranscript(record: TranscriptRecord): string {
  return record.role === "coach" ? String(record.say ?? "") : String(record.text ?? "");
}

export function transcriptToSimMessages(transcript: TranscriptRecord[]): SimMessage[] {
  return transcript.flatMap((record, index) => {
    if (record.role === "system") return [];
    const content = textForTranscript(record).trim();
    if (!content) return [];
    return [{
      id: `sim-message-${index}-${record.role}`,
      role: record.role === "learner" ? "user" as const : "assistant" as const,
      content,
      contentBlocks: [{ type: "text", id: `text-${index}`, content }],
      status: "complete" as const,
    }];
  });
}

export function draftToSimMessages(prompt: string): SimMessage[] {
  return [
    {
      id: "sim-draft-user",
      role: "user",
      content: prompt,
      contentBlocks: [{ type: "text", id: "draft-user-text", content: prompt }],
      status: "complete",
    },
    {
      id: "sim-draft-status",
      role: "assistant",
      content: "当前自由 Prompt 规划能力尚未接入 LingxiGraph；此页面保留为 Sim 风格的占位会话。",
      contentBlocks: [{ type: "status", id: "draft-status", content: "未连接后端任务", status: "complete" }],
      status: "complete",
    },
  ];
}

function lastAssistantContent(messages: SimMessage[]): string {
  return [...messages].reverse().find((message) => message.role === "assistant")?.content ?? "";
}

function liveDelta(events: RunEvent[], messages: SimMessage[]): string {
  const delta = events
    .filter((event) => event.kind === "assistant.delta")
    .sort((a, b) => a.sequence - b.sequence)
    .map((event) => String(event.payload.delta ?? ""))
    .join("");
  if (!delta.trim()) return "";
  const previous = lastAssistantContent(messages);
  return previous.endsWith(delta) || delta.endsWith(previous) ? "" : delta;
}

export function sessionToSimMessages(session: SessionSnapshot, events: RunEvent[] = []): SimMessage[] {
  const messages = transcriptToSimMessages(session.transcript ?? []);
  const delta = liveDelta(events, messages);
  if (!delta) return messages;
  return [...messages, {
    id: `sim-live-${session.id}-${Math.max(...events.map((event) => event.sequence), 0)}`,
    role: "assistant",
    content: delta,
    contentBlocks: [{ type: "text", id: "live-text", content: delta }],
    status: "streaming",
  }];
}

function toolCallFromRunEvent(event: RunEvent): SimToolCall | null {
  if (event.kind !== "tool.started" && event.kind !== "tool.completed") return null;
  const name = String(event.payload.tool ?? "tool");
  const ok = event.payload.ok !== false;
  return {
    id: `tool-${name}`,
    name,
    displayTitle: name,
    status: event.kind === "tool.started" ? "executing" : ok ? "success" : "error",
    detail: event.kind === "tool.completed"
      ? ok
        ? event.payload.duration_ms === undefined ? "完成" : `完成 · ${String(event.payload.duration_ms)} ms`
        : String(event.payload.error ?? "工具执行失败")
      : undefined,
  };
}

export function runEventsToSimActivity(events: RunEvent[], session?: SessionSnapshot | null): SimActivity {
  const ordered = [...events].sort((a, b) => a.sequence - b.sequence);
  const tools = new Map<string, SimToolCall>();
  let plan = session?.plan ?? [];
  let summary = "等待任务状态";
  let error: string | undefined;

  for (const event of ordered) {
    if (event.kind === "plan.ready" && Array.isArray(event.payload.steps)) plan = event.payload.steps.map(String);
    const tool = toolCallFromRunEvent(event);
    if (tool) tools.set(tool.name, tool);
    if (event.kind === "run.failed") error = String(event.payload.detail ?? event.payload.message ?? "任务运行失败");
    if (event.kind === "node.started") summary = `正在执行 ${event.node || "下一步"}`;
    if (event.kind === "assistant.delta") summary = "正在生成响应";
  }

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
    summary: error ?? phaseText[session?.phase ?? ""] ?? summary,
    plan,
    tools: [...tools.values()],
    evidence: (session?.evidence ?? []).map(({ id, summary: evidenceSummary, source }) => ({ id, summary: evidenceSummary, source })),
    running: session?.status === "running",
    error,
  };
}

export function agentTaskToSimMessages(task: AgentTaskSnapshot, events: AgentTaskEvent[] = []): SimMessage[] {
  const blocks: SimContentBlock[] = [];
  for (const event of [...events].sort((a, b) => a.sequence - b.sequence)) {
    if (event.kind === "agent.started" || event.kind === "agent.completed" || event.kind === "agent.failed") {
      const status = event.kind === "agent.failed" ? "error" : event.kind === "agent.completed" ? "complete" : "running";
      blocks.push({ type: "subagent", id: `agent-${event.sequence}`, agent: event.agent, title: event.agent, status });
    }
    if (event.kind === "artifact.ready") {
      blocks.push({ type: "resource", id: `artifact-${event.sequence}`, title: String(event.payload.kind ?? "学习产物"), status: "complete" });
    }
  }
  const status = task.status === "failed" ? "error" : task.status === "completed" || task.status === "partial" ? "complete" : "streaming";
  const blockStatus = status === "streaming" ? "running" : status;
  return [
    {
      id: `sim-task-prompt-${task.id}`,
      role: "user",
      content: task.prompt,
      contentBlocks: [{ type: "text", id: `prompt-${task.id}`, content: task.prompt }],
      status: "complete",
    },
    {
      id: `sim-task-result-${task.id}`,
      role: "assistant",
      content: task.intent.topic ? `正在围绕“${task.intent.topic}”准备学习产物。` : "正在准备学习产物。",
      contentBlocks: blocks.length ? blocks : [{ type: "status", id: `status-${task.id}`, content: task.error || "Agent 正在处理任务", status: blockStatus }],
      status,
    },
  ];
}

export function agentTaskToSimResources(task: AgentTaskSnapshot | null): SimResourceDescriptor[] {
  if (!task) return [];
  return [
    { id: `${task.id}-background`, title: "背景文档", kind: "background", available: task.artifacts.background.available, description: "lecture-hook Agent 生成的来源与背景文档" },
    { id: `${task.id}-visual`, title: "可视化讲解", kind: "visual", available: task.artifacts.visual.available, description: "visual-explainer Agent 生成的交互式讲解" },
  ];
}

export function dedupeSimEvents<T extends { sequence: number }>(events: T[]): T[] {
  return [...new Map(events.map((event) => [event.sequence, event])).values()].sort((a, b) => a.sequence - b.sequence);
}
