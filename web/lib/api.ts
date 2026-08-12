import type {
  AgentTaskEvent,
  AgentTaskSnapshot,
  Pack,
  RunEvent,
  SessionListItem,
  SessionSnapshot,
  SimAction,
  SimState,
} from "./types";

/**
 * When the app is served by FastAPI (the single-process deployment) the API is
 * same-origin and this is empty. Point NEXT_PUBLIC_API_BASE at the backend when
 * running `next dev` against a separately hosted server.
 */
// Separate local development runs Next.js on :3000 and FastAPI on :8000.
// Keep production/static deployment same-origin, but make `npm run dev`
// work without requiring every terminal to export an environment variable.
const configuredApiBase = process.env.NEXT_PUBLIC_API_BASE?.trim();
export const API_BASE =
  configuredApiBase ||
  (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(detail || `HTTP ${status}`);
  }
}

export type AccessTokenProvider = () => string | null | Promise<string | null>;

// The host application owns login/refresh.  LingxiLearn keeps only this
// in-memory callback and never persists an access token in browser storage.
let accessTokenProvider: AccessTokenProvider = () => null;

export function setAccessTokenProvider(provider: AccessTokenProvider): () => void {
  const previous = accessTokenProvider;
  accessTokenProvider = provider;
  return () => { accessTokenProvider = previous; };
}

function apiUrl(path: string): string {
  return `${API_BASE}/api${path}`;
}

async function authorizedFetch(url: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers);
  const token = await accessTokenProvider();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(url, { ...init, headers });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");
  const response = await authorizedFetch(apiUrl(path), { ...init, headers });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep the status text */
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () =>
    request<{ status: string; brain: string; agent: { configured: boolean; model: string }; packs: string[]; tools: number }>("/health"),

  packs: () => request<{ packs: Pack[] }>("/packs"),

  createSession: (missionId: string, packId = "computer-networks") =>
    request<{ id: string; mission_id: string; pack_id: string; status: string }>("/sessions", {
      method: "POST",
      body: JSON.stringify({ mission_id: missionId, pack_id: packId }),
    }),

  session: (id: string) => request<SessionSnapshot>(`/sessions/${id}`),

  answer: (id: string, answer: unknown) =>
    request<{ status: string }>(`/sessions/${id}/answer`, {
      method: "POST",
      body: JSON.stringify({ answer }),
    }),

  report: (id: string) => request<Record<string, any>>(`/sessions/${id}/report`),

  createAgentTask: (prompt: string) =>
    request<{ id: string; status: string }>("/agent-tasks", {
      method: "POST",
      body: JSON.stringify({ prompt }),
    }),

  agentTask: (id: string) => request<AgentTaskSnapshot>(`/agent-tasks/${id}`),

  agentArtifactUrl: (taskId: string, kind: "background" | "visual") =>
    `${API_BASE}/api/agent-tasks/${taskId}/artifacts/${kind}`,

  context: () => request<{
    profile: Record<string, unknown>;
    mastery: Record<string, number>;
    misconceptions: Record<string, unknown>[];
    preferences: Record<string, unknown>;
  }>("/me/context"),

  mastery: () =>
    request<{ mastery: Record<string, number>; sessions: SessionListItem[] }>("/me/mastery"),

  preferences: () =>
    request<{ preferences: Record<string, unknown> }>("/me/preferences"),

  updatePreferences: (patch: Record<string, unknown>) =>
    request<{ preferences: Record<string, unknown> }>("/me/preferences", {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),

  artifactUrl: (sessionId: string, artifactId: string) =>
    `${API_BASE}/api/sessions/${sessionId}/artifact/${artifactId}`,

  simInit: (scenario: string, seed: number) =>
    request<SimState>("/sim/init", {
      method: "POST",
      body: JSON.stringify({ scenario, seed }),
    }),

  simStep: (state: SimState, action: SimAction) =>
    request<SimState>("/sim/step", {
      method: "POST",
      body: JSON.stringify({ state, action }),
  }),

  fetchArtifact: async (url: string): Promise<Blob> => {
    const response = await authorizedFetch(url.startsWith("/") ? apiUrl(url) : url);
    if (!response.ok) {
      throw new ApiError(response.status, response.statusText);
    }
    return response.blob();
  },
};

/**
 * Subscribe to a session's event stream.
 *
 * The server replays from a durable log, so reconnecting with the last sequence
 * we saw resumes exactly where we left off — no gap, no duplicates. That is why
 * this tracks `lastSequence` rather than trusting the socket to stay up.
 */
type SseOptions = { from?: number; onEnd?: (status: string) => void };

/**
 * Fetch-based SSE keeps the existing durable-log replay contract while making
 * it possible to attach the same Authorization header as normal API calls.
 */
function subscribeSse<T extends { sequence?: number }>(
  path: string,
  onEvent: (event: T) => void,
  options: SseOptions = {},
): () => void {
  let closed = false;
  let finished = false;
  let controller: AbortController | null = null;
  let retry: ReturnType<typeof setTimeout> | null = null;
  let lastSequence = options.from ?? 0;

  const scheduleReconnect = () => {
    if (!closed && !finished && !retry) {
      retry = setTimeout(() => {
        retry = null;
        void connect();
      }, 1200);
    }
  };

  const dispatch = (eventName: string, data: string) => {
    if (!data) return;
    if (eventName === "stream.end") {
      try {
        const payload = JSON.parse(data) as { status?: string };
        options.onEnd?.(payload.status ?? "unknown");
      } catch {
        options.onEnd?.("unknown");
      }
      finished = true;
      return;
    }
    try {
      const event = JSON.parse(data) as T;
      if (typeof event.sequence === "number") lastSequence = event.sequence;
      onEvent(event);
    } catch {
      /* Ignore malformed frames rather than losing the stream. */
    }
  };

  const connect = async () => {
    if (closed || finished) return;
    controller = new AbortController();
    try {
      const separator = path.includes("?") ? "&" : "?";
      const response = await authorizedFetch(
        apiUrl(`${path}${separator}last_event_id=${lastSequence}`),
        {
          signal: controller.signal,
          headers: {
            Accept: "text/event-stream",
            "Last-Event-ID": String(lastSequence),
          },
        },
      );
      if (!response.ok || !response.body) {
        if (response.status === 401 || response.status === 403 || response.status === 404) {
          finished = true;
          return;
        }
        scheduleReconnect();
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let eventName = "message";
      let dataLines: string[] = [];

      const consumeLine = (line: string) => {
        if (line === "") {
          dispatch(eventName, dataLines.join("\n"));
          eventName = "message";
          dataLines = [];
          return;
        }
        if (line.startsWith(":")) return;
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).replace(/^ /, ""));
      };

      while (!closed && !finished) {
        const chunk = await reader.read();
        if (chunk.done) {
          buffer += decoder.decode();
          if (buffer) consumeLine(buffer);
          break;
        }
        buffer += decoder.decode(chunk.value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) consumeLine(line.replace(/\r$/, ""));
      }
      reader.releaseLock();
      if (!closed && !finished) scheduleReconnect();
    } catch (cause) {
      if (!closed && !(cause instanceof DOMException && cause.name === "AbortError")) {
        scheduleReconnect();
      }
    } finally {
      controller = null;
    }
  };

  void connect();
  return () => {
    closed = true;
    if (retry) clearTimeout(retry);
    retry = null;
    controller?.abort();
  };
}

export function subscribeEvents(
  sessionId: string,
  onEvent: (event: RunEvent) => void,
  options: SseOptions = {},
): () => void {
  return subscribeSse(`/sessions/${sessionId}/events`, onEvent, options);
}

export function subscribeAgentEvents(
  taskId: string,
  onEvent: (event: AgentTaskEvent) => void,
  options: SseOptions = {},
): () => void {
  return subscribeSse(`/agent-tasks/${taskId}/events`, onEvent, options);
}

export const KNOWN_EVENT_KINDS = [
  "run.started",
  "run.ended",
  "run.failed",
  "run.paused",
  "node.started",
  "node.completed",
  "node.retrying",
  "interrupt.raised",
  "assistant.delta",
  "stage.changed",
  "tool.started",
  "tool.completed",
  "evidence.added",
  "coach.move",
  "hint.escalated",
  "answer.judged",
  "mastery.updated",
  "probe.graded",
  "verify.graded",
  "step.completed",
  "plan.ready",
  "report.ready",
];

export const KNOWN_AGENT_EVENT_KINDS = [
  "task.started",
  "intent.started",
  "intent.completed",
  "agent.started",
  "agent.completed",
  "agent.failed",
  "artifact.ready",
  "task.completed",
  "task.failed",
];
