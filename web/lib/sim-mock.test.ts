import { describe, expect, it } from "vitest";
import { appendMockTurn, createMockRun, mockSidebarData, SIM_NATIVE_CAPABILITIES } from "@/lib/sim-mock";

describe("sim placeholder mode", () => {
  it("creates deterministic Sim messages, tools, sub-agents and orchestration graph", () => {
    const run = createMockRun("解释 TCP 重传");
    expect(run.messages.map((message) => message.role)).toEqual(["user", "assistant"]);
    expect(run.messages[1].contentBlocks.map((block) => block.type)).toContain("subagent");
    expect(run.messages[1].contentBlocks.map((block) => block.type)).toContain("tool_call");
    expect(run.graph.nodes.map((node) => node.id)).toEqual(["input", "intent", "research", "search", "inspect", "resource"]);
    expect(run.activity.tools.every((item) => item.status === "success")).toBe(true);
    expect(run.activity.summary).toContain("未调用");
  });

  it("lists every native capability as an explicit placeholder", () => {
    const run = createMockRun();
    expect(run.capabilities).toEqual(SIM_NATIVE_CAPABILITIES);
    expect(run.capabilities.length).toBeGreaterThanOrEqual(20);
    expect(run.capabilities.every((capability) => capability.status === "placeholder")).toBe(true);
  });

  it("appends another local turn without changing the conversation id", () => {
    const first = createMockRun("first");
    const next = appendMockTurn(first, "second");
    expect(next.id).toBe(first.id);
    expect(next.messages).toHaveLength(4);
    expect(next.messages[2].content).toBe("second");
    expect(next.log.length).toBeGreaterThan(first.log.length);
  });

  it("provides sidebar placeholders without catalogue or session requests", () => {
    const sidebar = mockSidebarData();
    expect(sidebar.loading).toBe(false);
    expect(sidebar.sessions).toHaveLength(2);
    expect(sidebar.missions).toHaveLength(2);
  });
});
