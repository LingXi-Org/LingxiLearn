import { describe, expect, it } from "vitest";
import {
  agentTaskToCanvasGraph,
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
    visual_explainer: { status: "pending" },
  },
  artifacts: {
    background: { available: false, url: "" },
    visual: { available: true, url: "", metadata: { title: "TCP 可视化" } },
  },
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
      { sequence: 4, kind: "agent.completed", agent: "visual_explainer", payload: {}, ts: null },
      { sequence: 5, kind: "task.completed", agent: "coordinator", payload: { status: "completed" }, ts: null },
    ]);
    expect(graph.nodes.map((node) => node.id)).toEqual(["input", "intent", "lecture_hook", "visual_explainer", "merge"]);
    expect(graph.nodes.find((node) => node.id === "lecture_hook")?.status).toBe("running");
    expect(graph.nodes.find((node) => node.id === "visual_explainer")?.status).toBe("complete");
    expect(graph.edges.filter((edge) => edge.from === "intent")).toHaveLength(2);
  });

  it("streams key event output instead of static task cards", () => {
    const messages = agentTaskToSimMessages(task(), [
      { sequence: 1, kind: "agent.started", agent: "lecture_hook", payload: {}, ts: null },
    ]);
    expect(messages.map((message) => message.role)).toEqual(["user", "assistant"]);
    expect(messages[1].contentBlocks.map((block) => block.type)).toEqual(["text"]);
    expect(messages[1].content).toContain("课程引入设计 Agent 已接收任务");
    expect(agentTaskToSimResources(task()).map((resource) => resource.kind)).toEqual(["background", "visual"]);
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
