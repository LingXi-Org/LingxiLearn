import type { AgentTaskEvent, AgentTaskSnapshot } from "@/lib/types";

export type SimBlockType = "text" | "subagent" | "status" | "resource";

export interface SimContentBlock {
  type: SimBlockType;
  id: string;
  content?: string;
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

export interface SimActivityTool {
  id: string;
  displayTitle: string;
  detail?: string;
  status: "executing" | "success" | "error";
}

export interface SimActivity {
  summary: string;
  agents: SimAgentRun[];
  tools: SimActivityTool[];
  evidence: Array<{ id: string; summary: string; source: string }>;
  running: boolean;
  error?: string;
}

export interface SimResourceDescriptor {
  id: string;
  title: string;
  kind: "background" | "visual";
  available: boolean;
  description: string;
}

export type AgentCanvasNodeKind = "input" | "intent" | "agent" | "merge";
export type AgentCanvasStatus = "pending" | "running" | "complete" | "error";

export interface AgentCanvasNode {
  id: string;
  label: string;
  kind: AgentCanvasNodeKind;
  status: AgentCanvasStatus;
  detail: string;
}

export interface AgentCanvasEdge {
  from: string;
  to: string;
  label: string;
}

export interface AgentCanvasGraph {
  nodes: AgentCanvasNode[];
  edges: AgentCanvasEdge[];
}

export interface SimAgentRunItem {
  id: string;
  content: string;
  status: "running" | "complete" | "error";
}

export interface SimAgentRun {
  id: string;
  agent: string;
  label: string;
  status: "running" | "complete" | "error";
  items: SimAgentRunItem[];
}

const TERMINAL_STATUSES = new Set(["completed", "partial", "failed"]);

function statusForSnapshot(
  snapshot: AgentTaskSnapshot["agents"][keyof AgentTaskSnapshot["agents"]],
): AgentCanvasStatus {
  if (snapshot.status === "completed") return "complete";
  if (snapshot.status === "failed") return "error";
  return "pending";
}

function eventStatus(
  events: AgentTaskEvent[],
  agent: string,
  current: AgentCanvasStatus,
): AgentCanvasStatus {
  const relevant = events
    .filter((event) => event.agent === agent || (agent === "intent" && event.kind.startsWith("intent.")))
    .sort((a, b) => a.sequence - b.sequence);
  let status = current;
  for (const event of relevant) {
    if (event.kind.endsWith(".started")) status = "running";
    if (event.kind.endsWith(".completed")) status = "complete";
    if (event.kind.endsWith(".failed")) status = "error";
  }
  return status;
}

export function agentTaskToCanvasGraph(
  task: AgentTaskSnapshot | null,
  events: AgentTaskEvent[] = [],
): AgentCanvasGraph {
  if (!task) {
    return {
      nodes: [],
      edges: [],
    };
  }

  const orderedEvents = dedupeSimEvents(events);
  const agentIds = [...new Set(orderedEvents.map((event) => event.agent).filter((agent) => agent && agent !== "coordinator"))];
  const nodes: AgentCanvasNode[] = [{ id: "input", label: "User input", kind: "input", status: "complete", detail: task.prompt }];
  for (const agent of agentIds) {
    const snapshot = agent === "intent" ? task.agents.intent : agent === "lecture_hook" ? task.agents.lecture_hook : agent === "visual_explainer" ? task.agents.visual_explainer : { status: "pending" as const };
    const relevant = orderedEvents.filter((event) => event.agent === agent);
    const latest = relevant.at(-1);
    nodes.push({
      id: agent,
      label: agentLabel(agent),
      kind: agent === "intent" ? "intent" : "agent",
      status: eventStatus(orderedEvents, agent, statusForSnapshot(snapshot)),
      detail: latest ? eventLine(latest, task) : "等待执行",
    });
  }
  const terminal = TERMINAL_STATUSES.has(task.status) || orderedEvents.some((event) => event.kind === "task.completed" || event.kind === "task.failed");
  if (terminal) nodes.push({ id: "merge", label: "Merge results", kind: "merge", status: task.status === "failed" ? "error" : "complete", detail: task.error || "汇总当前 Agent 产物" });

  const edges: AgentCanvasEdge[] = [];
  const intent = agentIds.includes("intent") ? "intent" : agentIds[0];
  if (intent) edges.push({ from: "input", to: intent, label: "识别" });
  const specialists = agentIds.filter((agent) => agent !== intent);
  for (const agent of specialists) edges.push({ from: intent || "input", to: agent, label: "分发" });
  if (terminal) for (const agent of specialists.length ? specialists : intent ? [intent] : []) edges.push({ from: agent, to: "merge", label: "产物" });
  return { nodes, edges };
}

function taskStatus(task: AgentTaskSnapshot): SimMessage["status"] {
  if (task.status === "failed") return "error";
  if (TERMINAL_STATUSES.has(task.status)) return "complete";
  return "streaming";
}

export function draftToSimMessages(prompt: string): SimMessage[] {
  return [
    {
      id: "draft-user",
      role: "user",
      content: prompt,
      contentBlocks: [{ type: "text", id: "draft-user-text", content: prompt }],
      status: "complete",
    },
    {
      id: "draft-status",
      role: "assistant",
      content: "正在创建 Agent 任务…",
      contentBlocks: [{ type: "status", id: "draft-status-block", content: "正在创建 Agent 任务…", status: "running" }],
      status: "streaming",
    },
  ];
}

export function agentTaskToSimMessages(task: AgentTaskSnapshot, events: AgentTaskEvent[] = []): SimMessage[] {
  const status = taskStatus(task);
  const lines = dedupeSimEvents(events).map((event) => eventLine(event, task)).filter(Boolean);
  const content = lines.join("\n") || "正在连接 Agent 事件流…";

  return [
    {
      id: `task-prompt-${task.id}`,
      role: "user",
      content: task.prompt,
      contentBlocks: [{ type: "text", id: `prompt-${task.id}`, content: task.prompt }],
      status: "complete",
    },
    {
      id: `task-result-${task.id}`,
      role: "assistant",
      content,
      contentBlocks: [{ type: "text", id: `task-stream-${task.id}`, content }],
      status,
    },
  ];
}

export function agentTaskToSimActivity(task: AgentTaskSnapshot | null, events: AgentTaskEvent[] = []): SimActivity {
  if (!task) return { summary: "", agents: [], tools: [], evidence: [], running: false };
  const latest = [...events].sort((a, b) => b.sequence - a.sequence)[0];
  const summary = task.status === "failed"
    ? task.error || "任务执行失败"
    : latest?.kind === "intent.started"
      ? "正在识别问题意图"
      : latest?.agent === "lecture_hook"
        ? "正在生成课堂 Hook 背景产物"
        : latest?.agent === "visual_explainer"
          ? "正在生成交互式可视化页面"
          : task.status === "completed"
            ? "两个 Agent 已完成"
            : "任务正在执行";
  return {
    summary,
    agents: agentTaskToAgentRuns(task, events),
    tools: [],
    evidence: [],
    running: task.status === "queued" || task.status === "running",
    error: task.error || undefined,
  };
}

export function agentTaskToAgentRuns(task: AgentTaskSnapshot, events: AgentTaskEvent[]): SimAgentRun[] {
  const ordered = dedupeSimEvents(events).filter((event) => event.agent && event.agent !== "coordinator");
  return [...new Set(ordered.map((event) => event.agent))].map((agent) => {
    const relevant = ordered.filter((event) => event.agent === agent);
    const failed = relevant.some((event) => event.kind.endsWith("failed"));
    const complete = relevant.some((event) => event.kind.endsWith("completed"));
    return {
      id: `run-${agent}`,
      agent,
      label: agentLabel(agent),
      status: failed ? "error" : complete ? "complete" : "running",
      items: relevant.map((event) => ({ id: `${event.sequence}-${event.kind}`, content: eventLine(event, task), status: event.kind.endsWith("failed") ? "error" : event.kind.endsWith("completed") || event.kind === "artifact.ready" ? "complete" : "running" })),
    };
  });
}

export function agentLabel(agent: string): string {
  if (agent === "intent") return "Intent Recognizer";
  if (agent === "lecture_hook") return "课程引入设计 Agent";
  if (agent === "visual_explainer") return "交互式可视化讲解 Agent";
  return agent.split(/[_-]/).map((part) => part ? `${part[0].toUpperCase()}${part.slice(1)}` : "").join(" ");
}

function eventLine(event: AgentTaskEvent, task: AgentTaskSnapshot): string {
  const message = typeof event.payload.message === "string" ? event.payload.message : "";
  if (event.kind === "task.started") return "任务已创建，正在启动意图识别。";
  if (event.kind === "intent.started") return "正在识别问题意图…";
  if (event.kind === "intent.completed") return `已识别主题：“${String(event.payload.topic || task.intent.topic || "未命名主题")}”。`;
  if (event.kind === "agent.started") return `${agentLabel(event.agent)} 已接收任务，开始执行。`;
  if (event.kind === "agent.output") return message || `${agentLabel(event.agent)} 生成了新的关键输出。`;
  if (event.kind === "artifact.ready") return `${agentLabel(event.agent)} 的${event.payload.artifact === "visual" ? "交互页面" : "背景产物"}已就绪。`;
  if (event.kind === "agent.completed") return `${agentLabel(event.agent)} 已完成。`;
  if (event.kind === "agent.failed") return `${agentLabel(event.agent)} 执行失败：${message || String(event.payload.error || "未知错误")}`;
  if (event.kind === "task.completed") return event.payload.status === "partial" ? "任务部分完成，可查看当前已生成产物。" : "所有 Agent 已完成。";
  if (event.kind === "task.failed") return message || task.error || "任务执行失败。";
  return "";
}

export function agentTaskToSimResources(task: AgentTaskSnapshot | null): SimResourceDescriptor[] {
  if (!task) return [];
  return [
    { id: `${task.id}-background`, title: "课程引入设计", kind: "background", available: task.artifacts.background.available, description: "课程引入设计 Agent 生成的独立 HTML 页面" },
    { id: `${task.id}-visual`, title: "交互式可视化讲解页面", kind: "visual", available: task.artifacts.visual.available, description: "交互式可视化讲解 Agent 生成的独立 HTML 页面" },
  ];
}

export function dedupeSimEvents<T extends { sequence: number }>(events: T[]): T[] {
  return [...new Map(events.map((event) => [event.sequence, event])).values()].sort((a, b) => a.sequence - b.sequence);
}
