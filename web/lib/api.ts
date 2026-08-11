import type { Pack, RunEvent, SessionListItem, SessionSnapshot, SimAction, SimState } from "./types";

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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
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
    request<{ status: string; brain: string; packs: string[]; tools: number }>("/health"),

  packs: () => request<{ packs: Pack[] }>("/packs"),

  createSession: (missionId: string, packId = "computer-networks", learnerId = "") =>
    request<{ id: string; learner_id: string; status: string }>("/sessions", {
      method: "POST",
      body: JSON.stringify({ mission_id: missionId, pack_id: packId, learner_id: learnerId }),
    }),

  session: (id: string) => request<SessionSnapshot>(`/sessions/${id}`),

  answer: (id: string, answer: unknown) =>
    request<{ status: string }>(`/sessions/${id}/answer`, {
      method: "POST",
      body: JSON.stringify({ answer }),
    }),

  report: (id: string) => request<Record<string, any>>(`/sessions/${id}/report`),

  mastery: (learnerId: string) =>
    request<{ learner_id: string; mastery: unknown[]; sessions: SessionListItem[] }>(`/learners/${learnerId}/mastery`),

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
};

/**
 * Subscribe to a session's event stream.
 *
 * The server replays from a durable log, so reconnecting with the last sequence
 * we saw resumes exactly where we left off — no gap, no duplicates. That is why
 * this tracks `lastSequence` rather than trusting the socket to stay up.
 */
export function subscribeEvents(
  sessionId: string,
  onEvent: (event: RunEvent) => void,
  options: { from?: number; onEnd?: (status: string) => void } = {},
): () => void {
  let closed = false;
  let source: EventSource | null = null;
  let lastSequence = options.from ?? 0;
  let retry: ReturnType<typeof setTimeout> | null = null;

  const connect = () => {
    if (closed) return;
    const url = `${API_BASE}/api/sessions/${sessionId}/events?last_event_id=${lastSequence}`;
    source = new EventSource(url);

    source.onmessage = (message) => {
      try {
        const event = JSON.parse(message.data) as RunEvent;
        if (typeof event.sequence === "number") lastSequence = event.sequence;
        onEvent(event);
      } catch {
        /* ignore malformed frames rather than tearing down the stream */
      }
    };

    // Named events arrive with `event: <kind>`; onmessage only sees unnamed
    // ones, so the server's kind-named frames need an explicit listener.
    const handler = (message: MessageEvent) => {
      try {
        const event = JSON.parse(message.data) as RunEvent;
        if (typeof event.sequence === "number") lastSequence = event.sequence;
        onEvent(event);
      } catch {
        /* ignore */
      }
    };
    for (const kind of KNOWN_EVENT_KINDS) source.addEventListener(kind, handler as EventListener);

    source.addEventListener("stream.end", (message) => {
      const data = JSON.parse((message as MessageEvent).data ?? "{}");
      options.onEnd?.(data.status ?? "unknown");
      source?.close();
      source = null;
    });

    source.onerror = () => {
      source?.close();
      source = null;
      if (!closed) retry = setTimeout(connect, 1200);
    };
  };

  connect();
  return () => {
    closed = true;
    if (retry) clearTimeout(retry);
    source?.close();
  };
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
