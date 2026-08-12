import type { Mission, SessionListItem } from "@/lib/types";
import type { SimActivity, SimContentBlock, SimMessage, SimResourceDescriptor, SimToolCall } from "@/lib/sim-adapter";

export interface SimMockGraphNode {
  id: string;
  label: string;
  kind: "router" | "agent" | "tool" | "resource";
  status: "complete" | "placeholder";
  detail: string;
}

export interface SimMockGraphEdge {
  from: string;
  to: string;
  label: string;
}

export interface SimMockCapability {
  id: string;
  title: string;
  category: "conversation" | "agent" | "workspace" | "platform";
  status: "placeholder";
  description: string;
}

export interface SimMockRun {
  id: string;
  prompt: string;
  title: string;
  messages: SimMessage[];
  activity: SimActivity;
  graph: { nodes: SimMockGraphNode[]; edges: SimMockGraphEdge[] };
  resources: SimResourceDescriptor[];
  capabilities: SimMockCapability[];
  log: string[];
}

const MOCK_TIME = "2026-01-01T00:00:00.000Z";

export const SIM_NATIVE_CAPABILITIES: SimMockCapability[] = [
  { id: "conversation", title: "Chat conversation", category: "conversation", status: "placeholder", description: "Sim 对话消息、流式文本和消息操作的占位实现。" },
  { id: "composer", title: "Prompt composer", category: "conversation", status: "placeholder", description: "输入框、停止生成、快捷操作和模型选择的占位实现。" },
  { id: "attachments", title: "Attachments", category: "conversation", status: "placeholder", description: "附件选择与上传入口保留占位，不读取真实文件。" },
  { id: "subagents", title: "Sub-agents", category: "agent", status: "placeholder", description: "子 Agent 卡片与生命周期状态的占位实现。" },
  { id: "tools", title: "Tool calls", category: "agent", status: "placeholder", description: "工具调用、参数、结果和错误状态的占位实现。" },
  { id: "orchestration", title: "Agent orchestration", category: "agent", status: "placeholder", description: "Agent 编排节点、边和执行顺序的可视化占位实现。" },
  { id: "workflows", title: "Workflows", category: "agent", status: "placeholder", description: "工作流浏览、创建和运行入口的占位实现。" },
  { id: "skills", title: "Skills", category: "agent", status: "placeholder", description: "技能选择与技能执行的占位实现。" },
  { id: "browser", title: "Browser tool", category: "agent", status: "placeholder", description: "浏览器工具入口保留占位，不发起网络请求。" },
  { id: "terminal", title: "Terminal tool", category: "agent", status: "placeholder", description: "终端工具入口保留占位，不执行命令。" },
  { id: "resources", title: "Resource panel", category: "workspace", status: "placeholder", description: "Sim 资源面板与资源标签页的占位实现。" },
  { id: "files", title: "Files", category: "workspace", status: "placeholder", description: "文件资源浏览、预览和操作入口保留占位。" },
  { id: "tables", title: "Tables", category: "workspace", status: "placeholder", description: "表格资源渲染与编辑入口保留占位。" },
  { id: "knowledge", title: "Knowledge", category: "workspace", status: "placeholder", description: "知识库检索与引用入口保留占位。" },
  { id: "canvas", title: "Canvas / visual", category: "workspace", status: "placeholder", description: "画布、图表和可视化产物入口保留占位。" },
  { id: "command-search", title: "Command search", category: "platform", status: "placeholder", description: "命令搜索与快捷键面板的占位实现。" },
  { id: "integrations", title: "Integrations", category: "platform", status: "placeholder", description: "外部集成配置入口保留占位。" },
  { id: "schedules", title: "Schedules", category: "platform", status: "placeholder", description: "定时任务与后台运行入口保留占位。" },
  { id: "voice", title: "Voice", category: "platform", status: "placeholder", description: "语音输入输出入口保留占位，不访问麦克风。" },
  { id: "auth", title: "Authentication", category: "platform", status: "placeholder", description: "Sim 账户与鉴权入口保留占位，不启用 Better Auth。" },
  { id: "persistence", title: "Persistence", category: "platform", status: "placeholder", description: "会话保存、同步和历史记录入口保留占位。" },
];

const MOCK_MISSIONS: Mission[] = [
  {
    id: "sim-placeholder-networking",
    title: "Network reasoning workflow",
    subtitle: "Sim workflow placeholder",
    summary: "展示 Sim 工作流入口与 LingxiGraph 对齐占位。",
    why_not_chat: "当前仅用于演示 Sim 原生交互，不创建真实课程任务。",
    concepts: ["agent orchestration", "evidence", "resources"],
    estimated_minutes: 12,
    steps: 4,
  },
  {
    id: "sim-placeholder-agent-task",
    title: "Agent task workflow",
    subtitle: "Sub-agent placeholder",
    summary: "展示占位 Agent、工具调用和资源产物。",
    why_not_chat: "真实 Agent Task 尚未连接到 Sim 原生工作流协议。",
    concepts: ["sub-agents", "tool calls", "artifacts"],
    estimated_minutes: 8,
    steps: 3,
  },
];

export function mockSidebarData() {
  const missions = MOCK_MISSIONS.map((mission) => ({ mission, packId: "sim-placeholder-pack" }));
  const missionById = new Map(MOCK_MISSIONS.map((mission) => [mission.id, mission]));
  const sessions: SessionListItem[] = [
    { id: "mock-session-networking", mission_id: MOCK_MISSIONS[0].id, pack_id: "sim-placeholder-pack", status: "done", created_at: MOCK_TIME },
    { id: "mock-session-agent", mission_id: MOCK_MISSIONS[1].id, pack_id: "sim-placeholder-pack", status: "done", created_at: MOCK_TIME },
  ];
  return { sessions, missionById, missions, loading: false };
}

function tool(id: string, name: string, displayTitle: string, detail: string): SimToolCall {
  return { id, name, displayTitle, status: "success", detail, agent: "research-agent" };
}

function block(id: string, type: SimContentBlock["type"], content: string, extra: Partial<SimContentBlock> = {}): SimContentBlock {
  return { id, type, content, ...extra };
}

export function createMockRun(prompt = "New Sim conversation", sequence = 1): SimMockRun {
  const cleanPrompt = prompt.trim() || "New Sim conversation";
  const slug = cleanPrompt.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 32) || "conversation";
  const id = `mock-${slug}-${sequence}`;
  const tools = [
    tool(`${id}-search`, "knowledge.search", "Knowledge search", "placeholder result · no API call"),
    tool(`${id}-inspect`, "artifact.inspect", "Artifact inspect", "placeholder result · no file access"),
  ];
  const assistantText = `这是 Sim 原生 Agent 的占位输出：我已收到“${cleanPrompt}”。当前演示不会调用真实 API，而是展示 LingxiGraph 适配前的对话、工具、子 Agent、资源和编排状态。`;
  const messages: SimMessage[] = [
    {
      id: `${id}-user`, role: "user", content: cleanPrompt,
      contentBlocks: [block(`${id}-user-text`, "text", cleanPrompt)], status: "complete",
    },
    {
      id: `${id}-assistant`, role: "assistant", content: assistantText,
      contentBlocks: [
        block(`${id}-text`, "text", assistantText),
        block(`${id}-router`, "subagent", "Intent router · placeholder", { agent: "intent-router", title: "Intent router", status: "complete" }),
        block(`${id}-research`, "subagent", "Research agent · placeholder", { agent: "research-agent", title: "Research agent", status: "complete" }),
        block(`${id}-tools`, "tool_call", "Tool calls · placeholder", { toolCall: tools[0], status: "complete" }),
        block(`${id}-resource`, "resource", "Resource preview · placeholder", { title: "Sim Resource Panel", status: "complete" }),
        block(`${id}-status`, "status", "Completed locally · no LingxiGraph request", { status: "complete" }),
      ], status: "complete",
    },
  ];
  const activity: SimActivity = {
    summary: "占位 Agent 已完成本地演示编排；未调用 LingxiGraph 或外部 API。",
    plan: ["接收用户消息", "Intent router 分派", "Research agent 调用占位工具", "生成 Sim 资源与编排图"],
    tools,
    evidence: [
      { id: `${id}-evidence-1`, summary: "placeholder evidence · no source", source: "sim-mock" },
      { id: `${id}-evidence-2`, summary: "placeholder artifact · no source", source: "sim-mock" },
    ],
    running: false,
  };
  const graph = {
    nodes: [
      { id: "input", label: "User input", kind: "router" as const, status: "complete" as const, detail: cleanPrompt },
      { id: "intent", label: "Intent router", kind: "agent" as const, status: "placeholder" as const, detail: "placeholder agent" },
      { id: "research", label: "Research agent", kind: "agent" as const, status: "placeholder" as const, detail: "placeholder sub-agent" },
      { id: "search", label: "Knowledge search", kind: "tool" as const, status: "placeholder" as const, detail: "no API call" },
      { id: "inspect", label: "Artifact inspect", kind: "tool" as const, status: "placeholder" as const, detail: "no file access" },
      { id: "resource", label: "Resource panel", kind: "resource" as const, status: "placeholder" as const, detail: "Sim-native placeholder" },
    ],
    edges: [
      { from: "input", to: "intent", label: "route" },
      { from: "intent", to: "research", label: "delegate" },
      { from: "research", to: "search", label: "call" },
      { from: "research", to: "inspect", label: "call" },
      { from: "research", to: "resource", label: "publish" },
    ],
  };
  return {
    id, prompt: cleanPrompt, title: cleanPrompt.slice(0, 40), messages, activity, graph,
    resources: [
      { id: `${id}-conversation`, title: "Conversation transcript", kind: "learning-artifact", available: false, description: "Sim 原生消息资源占位；没有持久化。" },
      { id: `${id}-background`, title: "Background document", kind: "background", available: false, description: "没有接入真实文件或知识库。" },
      { id: `${id}-visual`, title: "Visual explanation", kind: "visual", available: false, description: "没有接入真实画布或可视化 Artifact。" },
    ],
    capabilities: SIM_NATIVE_CAPABILITIES,
    log: ["message.received · local mock", "agent.intent · placeholder", "agent.research · placeholder", "tool.* · no API call", "resource.published · placeholder", "run.completed · local mock"],
  };
}

export function appendMockTurn(run: SimMockRun, prompt: string): SimMockRun {
  const next = createMockRun(prompt, run.messages.length + 1);
  return { ...next, id: run.id, title: run.title, messages: [...run.messages, ...next.messages], log: [...run.log, ...next.log] };
}
