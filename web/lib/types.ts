/** Shapes mirrored from the server's API. Kept hand-written and small. */

export type SceneKind =
  | "probe"
  | "packet_lab"
  | "attribution"
  | "sim_console"
  | "verify"
  | "report";

export interface Choice {
  value: string;
  label: string;
}

export interface Item {
  id: string;
  concept: string;
  prompt: string;
  expects: string;
  choices: Choice[];
  difficulty: number;
}

export interface TutorMove {
  intent: "ask" | "hint" | "probe_back" | "confirm" | "reveal" | "wrap";
  say: string;
  hint_level: number;
  evidence_ids: string[];
  expects: string;
  choices: Choice[];
  rationale: string;
}

export interface Evidence {
  id: string;
  kind: "tool_result" | "knowledge" | "learner_action" | "simulation_frame";
  source: string;
  summary: string;
  locator: Record<string, unknown>;
  value: unknown;
  digest: string;
}

export interface Stage {
  scene: SceneKind;
  props: Record<string, any>;
  focus: string[];
}

export interface Pending {
  id: string;
  resumable: boolean;
  value: {
    kind: "probe" | "answer" | "verify";
    title?: string;
    items?: Item[];
    prompt?: TutorMove;
    stage?: Stage;
    step_id?: string;
    hint_level?: number;
    attempts?: number;
  };
}

export interface MasteryChange {
  concept: string;
  before: number;
  after: number;
  delta: number;
  reason: string;
  evidence_ids: string[];
}

export interface StepResult {
  step_id: string;
  concepts: string[];
  attempts: number;
  hint_level: number;
  correct: boolean;
  resolved: string;
  misconceptions: string[];
  evidence_ids: string[];
}

export interface Report {
  headline: string;
  strengths: string[];
  gaps: string[];
  next_steps: string[];
  citations: Record<string, string[]>;
  mission: string;
  mission_title: string;
  probe_score: number;
  verify_score: number;
  learning_gain: number;
  mastery_before: Record<string, number>;
  mastery_after: Record<string, number>;
  mastery_gain: Record<string, number>;
  misconceptions: string[];
  step_results: StepResult[];
  evidence_count: number;
}

export interface SessionSnapshot {
  id: string;
  status: "created" | "running" | "awaiting_learner" | "done" | "failed" | "cancelled";
  error: string;
  pack_id: string;
  pack_version: string;
  mission: {
    id: string;
    title: string;
    subtitle: string;
    why_not_chat: string;
    concepts: string[];
  };
  phase: string;
  stage: Stage;
  move: TutorMove;
  plan: string[];
  step_index: number;
  current_step: Record<string, any>;
  hint_level: number;
  attempts: number;
  answer_unlocked: boolean;
  mastery: Record<string, number>;
  mastery_before: Record<string, number>;
  mastery_changes: MasteryChange[];
  misconceptions: string[];
  evidence: Evidence[];
  transcript: any[];
  probe_score: number;
  verify_score: number;
  step_results: StepResult[];
  report: Report | Record<string, never>;
  pending: Pending | null;
  brain: string;
}

export interface Mission {
  id: string;
  title: string;
  subtitle: string;
  summary: string;
  why_not_chat: string;
  concepts: string[];
  estimated_minutes: number;
  steps: number;
}

export interface Pack {
  id: string;
  title: string;
  version: string;
  description: string;
  concepts: { id: string; title: string; summary: string; requires: string[] }[];
  missions: Mission[];
}

export interface RunEvent {
  sequence: number;
  kind: string;
  node: string;
  payload: Record<string, any>;
  ts: string;
}

// ---------------------------------------------------------------- simulator

export interface SimState {
  scenario: string;
  seed: number;
  tick: number;
  total_segments: number;
  window_size: number;
  base: number;
  next_seq: number;
  attempts: number[];
  inflight: {
    seq: number;
    sent_at: number;
    arrives_at: number;
    dropped: boolean;
    attempt: number;
    kind: "data" | "ack";
  }[];
  receiver_expected: number;
  receiver_buffer: number[];
  delivered: number;
  timer: { running: boolean; seq: number | null; expires_at: number | null };
  dup_ack_count: number;
  timeout_pending: boolean;
  events: { tick: number; kind: string; [k: string]: any }[];
  actions: { tick: number; op: string; seq?: number }[];
  done: boolean;
  brief: string;
  title: string;
}

export type SimAction =
  | { op: "send" }
  | { op: "wait" }
  | { op: "retransmit"; seq: number }
  | { op: "retransmit_all" };

// ---------------------------------------------------------------- capture

export interface Frame {
  number: number;
  ts: number;
  length: number;
  protocol: string;
  summary: string;
  layers: Record<string, any>;
  hex?: string;
}

export interface LadderData {
  hosts: string[];
  arrows: {
    frame: number;
    t_ms: number;
    src: string;
    dst: string;
    protocol: string;
    label: string;
    bytes: number;
  }[];
  span_ms: number;
  truncated: boolean;
}

export interface Waterfall {
  total_ms: number;
  accounted_ms: number;
  idle_ms: number;
  buckets: Record<string, number>;
  bucket_frames: Record<string, number[]>;
  frame_roles: Record<string, string>;
  primary_flow: string;
  anomalies: Record<string, any>[];
  flows: Record<string, any>[];
}

/** The learner's answer in the attribution mission: a split plus its evidence. */
export interface Attribution {
  allocations: Record<string, number>;
  pins: Record<string, number[]>;
}

export const BUCKETS = [
  { id: "dns", label: "DNS 解析", color: "var(--color-dns-500)" },
  { id: "tcp_connect", label: "TCP 建连", color: "var(--color-connect-500)" },
  { id: "ttfb", label: "请求等待", color: "var(--color-ttfb-500)" },
  { id: "transfer", label: "数据传输", color: "var(--color-transfer-500)" },
  { id: "retransmission", label: "重传停顿", color: "var(--color-retx-500)" },
] as const;

export const ROLE_COLORS: Record<string, string> = {
  dns_query: "var(--color-dns-500)",
  dns_response: "var(--color-dns-500)",
  tcp_syn: "var(--color-connect-500)",
  tcp_synack: "var(--color-connect-500)",
  tcp_ack: "var(--color-connect-500)",
  http_request: "var(--color-ttfb-500)",
  http_first_byte: "var(--color-ttfb-500)",
  http_response_data: "var(--color-transfer-500)",
  tcp_retransmission: "var(--color-retx-500)",
  tcp_duplicate_ack: "var(--color-retx-500)",
};
