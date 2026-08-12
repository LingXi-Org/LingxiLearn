import { describe, expect, it } from "vitest";
import {
  agentTaskToCanvasGraph,
  agentTaskToAgentRuns,
  agentTaskToSimActivity,
  agentTaskToSimMessages,
  agentTaskToSimResources,
  dedupeSimEvents,
  draftToSimMessages,
} from "@/lib/sim-adapter";
import type { AgentTaskSnapshot } from "@/lib/types";

const task = (overrides: Partial<AgentTaskSnapshot> = {}): AgentTaskSnapshot => ({
  id: "t-1",
  status: "running",
  prompt: "解释 TCP 重传",
  intent: { topic: "TCP", language: "zh" },
  agents: {
    intent: { status: "completed" },
    lecture_hook: { status: "pending" },
    interactive_lecture_deck: { status: "pending" },
    quiz_generator: { status: "pending" },
    interactive_visual_explainer: { status: "pending" },
  },
  artifacts: {
    lesson_intro: { available: true, url: "", metadata: { title: "课程引入" } },
    lecture_deck: { available: false, url: "" },
    quiz: { available: false },
    visual: { available: true, url: "", metadata: { title: "TCP 可视化" } },
  },
  quiz_submission: null,
  error: "",
  created_at: null,
  updated_at: null,
  ...overrides,
});

describe("agent task adapter", () => {
  it("grows the fan-out graph from live events", () => {
    const graph = agentTaskToCanvasGraph(task({ status: "completed" }), [
      { sequence: 1, kind: "intent.started", agent: "intent", payload: {}, ts: null },
      { sequence: 2, kind: "intent.completed", agent: "intent", payload: { topic: "TCP" }, ts: null },
      { sequence: 3, kind: "agent.started", agent: "lecture_hook", payload: {}, ts: null },
      { sequence: 4, kind: "agent.completed", agent: "interactive_lecture_deck", payload: {}, ts: null },
      { sequence: 5, kind: "task.completed", agent: "coordinator", payload: { status: "completed" }, ts: null },
    ]);
    expect(graph.nodes.map((node) => node.id)).toEqual(["input", "intent", "lecture_hook", "interactive_lecture_deck", "merge"]);
    expect(graph.nodes.find((node) => node.id === "lecture_hook")?.status).toBe("running");
    expect(graph.nodes.find((node) => node.id === "interactive_lecture_deck")?.status).toBe("complete");
    expect(graph.edges.filter((edge) => edge.from === "intent")).toHaveLength(2);
  });

  it("streams key event output instead of static task cards", () => {
    const messages = agentTaskToSimMessages(task(), [
      { sequence: 1, kind: "agent.started", agent: "lecture_hook", payload: {}, ts: null },
    ]);
    expect(messages.map((message) => message.role)).toEqual(["user", "assistant"]);
    expect(messages[1].contentBlocks.map((block) => block.type)).toEqual(["text"]);
    expect(messages[1].content).toContain("课程引入设计 Agent 已接收任务");
    expect(agentTaskToSimResources(task()).map((resource) => resource.kind)).toEqual(["lesson-intro", "lecture-deck", "quiz", "visual"]);
  });

  it("renders reasoning and tool lifecycle events in task output", () => {
    const events = [
      { sequence: 1, kind: "agent.started", agent: "lecture_hook", payload: {}, ts: null },
      { sequence: 2, kind: "reasoning.delta", agent: "lecture_hook", payload: { delta: "先阅读 skill" }, ts: null },
      { sequence: 3, kind: "tool.call.delta", agent: "lecture_hook", payload: { chunks: [{ name: "read_skill" }] }, ts: null },
      { sequence: 4, kind: "tool.result", agent: "lecture_hook", payload: { name: "read_skill", content: "已读取" }, ts: null },
    ];
    const messages = agentTaskToSimMessages(task(), events);
    expect(messages[1].content).toContain("思考 · 先阅读 skill");
    const run = agentTaskToAgentRuns(task(), events)[0];
    expect(run.groupItems?.some((item) => item.type === "tool" && item.title.startsWith("工具调用"))).toBe(true);
    expect(run.groupItems?.some((item) => item.type === "tool" && item.title.includes("工具结果"))).toBe(true);
    expect(agentTaskToSimActivity(task(), events).tools.map((tool) => tool.status)).toEqual(["executing", "success"]);
  });

  it("keeps only the latest reasoning item and redacts tool payloads", () => {
    const events = [
      { sequence: 1, kind: "reasoning.delta", agent: "lecture_hook", payload: { delta: "旧思考" }, ts: null },
      { sequence: 2, kind: "tool.result", agent: "lecture_hook", payload: { name: "read_skill", content: "完整 SKILL.md 私密内容" }, ts: null },
      { sequence: 3, kind: "reasoning.delta", agent: "lecture_hook", payload: { delta: "最新思考" }, ts: null },
    ];
    const run = agentTaskToAgentRuns(task(), events)[0];
    const reasoning = run.groupItems?.filter((item) => item.type === "reasoning");
    expect(reasoning).toHaveLength(1);
    expect(reasoning?.[0]).toMatchObject({ content: "最新思考" });
    const tool = run.groupItems?.find((item) => item.type === "tool");
    expect(tool?.type === "tool" ? tool.detail : "").not.toContain("完整 SKILL.md 私密内容");
    expect(tool?.type === "tool" ? tool.detail : "").toContain("内容已隐藏");
  });

  it("keeps an agent running after an intermediate model turn", () => {
    const events = [
      { sequence: 1, kind: "agent.started", agent: "lecture_hook", payload: { skill: "lesson-intro" }, ts: null },
      { sequence: 2, kind: "model.started", agent: "lecture_hook", payload: {}, ts: null },
      { sequence: 3, kind: "model.completed", agent: "lecture_hook", payload: { duration_ms: 1200 }, ts: null },
      { sequence: 4, kind: "tool.call.delta", agent: "lecture_hook", payload: { calls: [{ name: "read_skill" }] }, ts: null },
    ];
    expect(agentTaskToAgentRuns(task(), events)[0].status).toBe("running");
    expect(agentTaskToCanvasGraph(task(), events).nodes.find((node) => node.id === "lecture_hook")?.status).toBe("running");
  });

  it("reports partial and failed task states", () => {
    expect(agentTaskToSimActivity(task({ status: "partial" })).summary).toBe("任务正在执行");
    expect(agentTaskToSimActivity(task({ status: "failed", error: "模型不可用" })).summary).toBe("模型不可用");
    expect(agentTaskToSimMessages(task({ status: "failed", error: "模型不可用" }))[1].status).toBe("error");
  });

  it("creates a real-task draft while the POST is in flight", () => {
    expect(draftToSimMessages("解释 TCP")[1].content).toContain("创建 Agent 任务");
  });

  it("deduplicates replayed SSE sequences while preserving order", () => {
    expect(dedupeSimEvents([{ sequence: 2 }, { sequence: 1 }, { sequence: 2 }])).toEqual([{ sequence: 1 }, { sequence: 2 }]);
  });
});
