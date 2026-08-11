import { describe, expect, it } from "vitest";
import {
  classifyDraft,
  deriveArtifact,
  draftMessages,
  makeDraftArtifact,
  parseWorkspaceMode,
  reduceAgentActivity,
  transcriptToMessages,
} from "@/lib/workspace";
import type { RunEvent, SessionSnapshot } from "@/lib/types";

function session(overrides: Partial<SessionSnapshot> = {}): SessionSnapshot {
  return {
    id: "s-test",
    status: "awaiting_learner",
    error: "",
    pack_id: "computer-networks",
    pack_version: "1.0.0",
    mission: { id: "web-slow", title: "慢在哪一环", subtitle: "", why_not_chat: "", concepts: [] },
    phase: "await_learner",
    stage: { scene: "packet_lab", props: { frames: [] }, focus: [] },
    move: { intent: "ask", say: "看到了什么？", hint_level: 0, evidence_ids: [], expects: "text", choices: [], rationale: "" },
    plan: ["orient", "stall"],
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
    transcript: [],
    probe_score: 0,
    verify_score: 0,
    step_results: [],
    report: {},
    pending: null,
    brain: "scripted",
    ...overrides,
  };
}

describe("workspace route boundary", () => {
  it("prefers a real session id and parses an explicit draft", () => {
    expect(parseWorkspaceMode(new URLSearchParams("id=s-1&draft=1&prompt=x"))).toEqual({ kind: "session", sessionId: "s-1" });
    expect(parseWorkspaceMode(new URLSearchParams("draft=1&prompt=生成课程"))).toEqual({ kind: "draft", prompt: "生成课程" });
    expect(parseWorkspaceMode(new URLSearchParams())).toBeNull();
  });

  it("keeps unavailable prompts visibly mocked", () => {
    expect(classifyDraft("上传一道错题")).toBe("mistakes");
    expect(classifyDraft("为我生成课程大纲")).toBe("course");
    expect(draftMessages("生成课程")[1].text).toContain("没有执行");
    expect(makeDraftArtifact("生成课程")).toMatchObject({ source: "mock", status: "coming_soon", capability: "course" });
  });
});

describe("assistant-ui message adapter", () => {
  it("converts only learner and coach records", () => {
    const messages = transcriptToMessages([
      { role: "system", kind: "plan" },
      { role: "coach", say: "先看第 8 帧" },
      { role: "learner", text: "我觉得是服务器慢" },
    ]);
    expect(messages).toEqual([
      { id: "transcript-1-coach", role: "assistant", text: "先看第 8 帧" },
      { id: "transcript-2-learner", role: "user", text: "我觉得是服务器慢" },
    ]);
  });
});

describe("event and artifact projection", () => {
  it("reduces replayed tool events to one current tool state", () => {
    const events: RunEvent[] = [
      { sequence: 1, kind: "tool.started", node: "investigate", payload: { tool: "net.pcap.timeline" }, ts: "" },
      { sequence: 2, kind: "tool.completed", node: "investigate", payload: { tool: "net.pcap.timeline", ok: true, duration_ms: 12 }, ts: "" },
      { sequence: 2, kind: "tool.completed", node: "investigate", payload: { tool: "net.pcap.timeline", ok: true, duration_ms: 12 }, ts: "" },
    ];
    const activity = reduceAgentActivity(events, session());
    expect(activity.tools).toHaveLength(1);
    expect(activity.tools[0]).toMatchObject({ name: "net.pcap.timeline", state: "complete", detail: "完成 · 12 ms" });
  });

  it("maps stage scenes and terminal reports into typed artifacts", () => {
    expect(deriveArtifact(session()).kind).toBe("packet_lab");
    const done = session({
      phase: "done",
      status: "done",
      report: {
        headline: "你已经能用证据解释时延",
        strengths: [], gaps: [], next_steps: [], citations: {}, mission: "web-slow", mission_title: "慢在哪一环",
        probe_score: 0, verify_score: 1, learning_gain: 1, mastery_before: {}, mastery_after: {}, mastery_gain: {}, misconceptions: [], step_results: [], evidence_count: 0,
      },
    });
    expect(deriveArtifact(done)).toMatchObject({ kind: "report", source: "api", status: "ready" });
  });
});
