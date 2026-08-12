import { describe, expect, it } from "vitest";
import {
  agentTaskToSimMessages,
  agentTaskToSimResources,
  dedupeSimEvents,
  runEventsToSimActivity,
  sessionToSimMessages,
} from "@/lib/sim-adapter";
import type { AgentTaskSnapshot, SessionSnapshot } from "@/lib/types";

const session = (overrides: Partial<SessionSnapshot> = {}): SessionSnapshot => ({
  id: "s-1",
  status: "running",
  error: "",
  pack_id: "pack",
  pack_version: "1",
  mission: { id: "m", title: "任务", subtitle: "", why_not_chat: "", concepts: [] },
  phase: "investigate",
  stage: { scene: "packet_lab", props: {}, focus: [] },
  move: { intent: "ask", say: "下一步？", hint_level: 0, evidence_ids: [], expects: "text", choices: [], rationale: "" },
  plan: ["读取抓包"],
  step_index: 0,
  current_step: {},
  hint_level: 0,
  attempts: 0,
  answer_unlocked: false,
  mastery: {},
  mastery_before: {},
  mastery_changes: [],
  misconceptions: [],
  evidence: [],
  transcript: [{ role: "learner", text: "我先看 DNS" }, { role: "coach", say: "很好，先定位查询和响应。" }],
  probe_score: 0,
  verify_score: 0,
  step_results: [],
  report: {},
  pending: null,
  brain: "scripted",
  ...overrides,
});

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

describe("sim adapter", () => {
  it("converts transcript and live assistant deltas into Sim messages", () => {
    const messages = sessionToSimMessages(session(), [
      { sequence: 4, kind: "assistant.delta", node: "coach", payload: { delta: "继续观察 ACK。" }, ts: "" },
    ]);
    expect(messages.map((message) => message.role)).toEqual(["user", "assistant", "assistant"]);
    expect(messages.at(-1)?.status).toBe("streaming");
  });

  it("maps plan, tool lifecycle, evidence and failures", () => {
    const activity = runEventsToSimActivity([
      { sequence: 1, kind: "plan.ready", node: "plan", payload: { steps: ["检查 DNS", "检查 TCP"] }, ts: "" },
      { sequence: 2, kind: "tool.started", node: "investigate", payload: { tool: "pcap.analyze" }, ts: "" },
      { sequence: 3, kind: "tool.completed", node: "investigate", payload: { tool: "pcap.analyze", ok: true, duration_ms: 8 }, ts: "" },
      { sequence: 4, kind: "run.failed", node: "", payload: { detail: "失败" }, ts: "" },
    ], session());
    expect(activity.plan).toEqual(["检查 DNS", "检查 TCP"]);
    expect(activity.tools[0]).toMatchObject({ name: "pcap.analyze", status: "success" });
    expect(activity.error).toBe("失败");
  });

  it("turns Agent Task events into subagent/resource blocks", () => {
    const messages = agentTaskToSimMessages(task(), [
      { sequence: 1, kind: "agent.started", agent: "lecture_hook", payload: {}, ts: null },
      { sequence: 2, kind: "artifact.ready", agent: "lecture_hook", payload: { kind: "background" }, ts: null },
    ]);
    expect(messages[1].contentBlocks.map((block) => block.type)).toEqual(["subagent", "resource"]);
    expect(agentTaskToSimResources(task()).map((resource) => resource.id)).toEqual(["t-1-background", "t-1-visual"]);
  });

  it("deduplicates replayed SSE sequences while preserving order", () => {
    expect(dedupeSimEvents([{ sequence: 2 }, { sequence: 1 }, { sequence: 2 }])).toEqual([{ sequence: 1 }, { sequence: 2 }]);
  });
});
