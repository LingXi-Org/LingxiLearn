# Architecture

LingxiLearn is an AI teaching assistant for undergraduate engineering students.
The product thesis is a loop: understand where the learner is, run real tools on
a real artefact, coach without giving the answer away, verify they actually
learned it, and leave auditable evidence behind.

The architecture exists to make that loop true rather than merely claimed.

---

## 1. The layering rule

```
Next.js (static export)
        │  REST + SSE
FastAPI ├── EventProjector (pure)  ──►  run_events (durable log)
        │
Tutoring Kernel  ── LingxiGraph StateGraph, domain-agnostic
        │
        ├── Course Pack     declarative YAML: concepts, missions, rubrics
        └── Tool Registry   real deterministic computation
        │
lingxigraph 2.2.0 (PyPI) · SQLite | PostgreSQL
```

### Intent-driven Agent Tasks

Free-form questions use a durable difficult-knowledge subgraph.
`recognize_intent` normalizes the learner's topic, objective, level and duration,
then fans out to `lecture_hook` (`lesson-intro`) and
`interactive_lecture_deck` in the same graph tick. Both branches feed the
contract-only `quiz_generator`, after which the task waits for the learner.
Subsequent messages are routed through the same recognizer to answer, invoke the
general `interactive-visual-explainer`, submit once, or handoff to the main graph.

The specialists receive LingxiGraph 2.2.0 `FilesystemSkillSource` instances for
the vendored skills under `skills/`. The lecture branch gets only the public,
SSRF-checked web tools. The visual branch gets task-scoped HTML write/validate
tools; only `visual-explainer.html` under `var/agent_tasks/<task_id>/` is
allowed. The visual artifact is served with a sandboxed iframe and a strict CSP.

**The kernel knows nothing about any subject.** Its ten nodes are pedagogical
acts — `intake`, `diagnose`, `plan`, `investigate`, `coach`, `await_learner`,
`judge`, `advance`, `verify`, `report`. Not one mentions DNS, TCP or packets.

A subject enters through two seams:

- a **course pack** (`packs/<id>/`) declaring concepts, misconceptions, missions,
  steps, rubrics, hint ladders and knowledge;
- a **tool namespace** registered in the tool
  registry.

Adding 数据结构 or 操作系统 is a new directory plus a new namespace. It is not a
kernel change. New missions run through the same kernel while calling the tool
families declared by their course pack.

---

## 2. Why LingxiGraph, and how it is used

`lingxigraph` 2.2.0 is published on PyPI with **zero required runtime dependencies**,
so it is consumed as an ordinary dependency — no fork, no vendoring, no
submodule. The pieces used:

| Capability | Use |
|---|---|
| `StateGraph` + typed state | the teaching loop, with reducers on the evidence ledger |
| `interrupt()` / `Command(resume=…)` | human-in-the-loop, as durable thread state |
| `SqliteSaver` / `PostgresSaver` | session durability and restore |
| `stream_mode="events"` | the event stream the UI is projected from |
| `runtime.emit(channel, value)` | domain events, ridden on the `CUSTOM` channel |
| `@tool` | JSON Schema generation, reused by the LLM brains |
| `OpenAICompatChatModel`, `CozeChatModel` | both providers, one `ChatModel` protocol |

Behaviours verified against the runtime rather than assumed, and encoded in
`stream/projector.py`:

- `NODE_FAILED` is declared in the enum but **never emitted** — failures raise
  out of `astream`. Handling it would be dead code.
- `NODE_COMPLETED` carries the node's state delta under `data["update"]`.
- `NODE_RETRYING` carries the attempt under `data["value"]`.
- `CUSTOM` events arrive as `data={"channel", "value"}`.

---

## 3. The teaching kernel

```
START → intake → diagnose ──► plan ──► investigate ──┬─► coach → await_learner
                                                     │              ↓
                       ┌─────────────────────────────┘           judge
                       │                                            ↓
                    verify ◄──────── advance ◄─────────────────────┘
                       ↓                 │
                    report → END         └─► coach (retry) | investigate (next step)
```

`investigate` is the generic tool node: it reads `current_step.tools` from the
pack, resolves each name in the registry, executes it, and writes the results
into the evidence ledger. It never imports a domain module.

**One invariant matters when editing nodes.** A node that calls `interrupt()`
re-executes from the top when the run resumes. So nothing before an `interrupt()`
may emit a stream event or mutate anything outside the returned state delta —
otherwise the learner sees it twice on every resume. The evidence reducer
de-duplicates by id for the same reason.

### Personalisation

`plan` selects steps from the learner's mastery. A step may declare
`skip_if_mastered`, and a learner already above that threshold on every one of
its concepts skips it. Steps stay in authored order — later steps depend on
earlier tool output — so personalisation drops warm-ups rather than reshuffling
a sequence. Two learners, one mission, different paths; asserted in
`tests/test_kernel.py::test_two_learners_get_different_paths_on_one_mission`.

---

## 4. Not giving the answer away, as a mechanism

A system prompt asking a model to please not reveal the answer is not a
mechanism. Here it is one:

1. **The hint level is kernel state.** `advance` escalates it on a failed
   attempt; the brain is told the level, it does not choose it.
2. **Every step declares its own answer markers** (`leak_guard.phrases`,
   `leak_guard.numbers`) in the course pack.
3. **Every rendered coaching turn is post-validated** by
   `policy.check_leakage` before the learner sees it. Text is NFKC-folded and
   punctuation-stripped first, because Chinese has no word boundaries to anchor
   on; numbers match within a relative tolerance.
4. **A move that trips the guard is replaced** by the course author's hint at the
   current rung — which is guaranteed safe because a human wrote it.
5. **The walkthrough unlocks only on request after real attempts**
   (`should_unlock_answer`): reaching the attempt threshold is necessary but not
   sufficient, so the system never volunteers the answer to someone still
   working.

Because step 2 makes it checkable, leakage is *measured*, not asserted — see
`eval/report.md`.

---

## 5. Evidence, and why claims are cheap without it

Every tool result, knowledge citation and learner action
enters an append-only **ledger** with a stable id (`ev_0007`) and a content
digest. Teaching claims and report lines reference those ids; the UI resolves an
id back to its source.

Two enforcement points:

- `coach` drops citations that do not resolve before the move is shown.
- `report` discards any claim whose citations do not resolve, rather than
  shipping a report pointing at evidence that does not exist.

---

## 6. Grading is computed, never judged

`kernel/graders.py` holds a registry of deterministic graders. Correctness never
depends on a language model.

The interesting one is `attribution`, which grades mission 1 on two independent
axes:

1. **Allocation** — does each bucket match the waterfall our parser derived from
   the capture, within tolerance?
2. **Citation** — is every pinned frame real, and does it play the role claimed?

A citation that does not support its claim **gates** the result rather than
costing a fraction of the score. With five buckets, one bogus frame would
otherwise cost 0.2 and still pass — teaching exactly the habit the mission
exists to break.

Misconceptions fall out of *how* an answer is wrong: which bucket absorbed
misplaced time (`confusions`), or which protocol event a decision ignored
misconception flags. No model is asked to speculate about the learner's mind.

`sim_outcome` is graded by a tool run over the learner's *answer*: the submitted
action log is replayed from the seed server-side. The UI drives the console for
responsiveness, but a client cannot award itself goodput.

---

## 7. The network toolbox

Written from the RFCs rather than pulled from a library, for three reasons: the
captures are real `.pcap` files a student can open in Wireshark and check us
with; every cited field is one we decoded, so a frame number in a hint is
computed rather than recalled; and there is no real user traffic to anonymise.

- `codec.py` — Ethernet II / IPv4 / TCP / UDP / DNS / HTTP encode + decode, with
  correct checksums.

**The waterfall partitions the wall clock**: `dns + tcp_connect + ttfb +
transfer + retransmission + idle == total`. A budget that does not add up is a
budget you cannot grade against. Retransmission stall is carved *out of* the
transfer window rather than laid on top of it, because that stall is precisely
what learners misfile as "the server is slow".

---

## 8. Streaming that survives a real network

- `EventProjector` is a pure synchronous function over `Event` → `Emission`,
  with no web or database imports, de-duplicating on `(run_id, sequence)`. The
  entire mapping is unit-tested against fabricated events.
- Projections are persisted to `run_events` with a monotonic per-session
  sequence. **SSE serves from that log, not from the live run**, so
  `Last-Event-ID` resumption falls out for free.
- **Interrupts are durable thread state**, read back from the checkpoint and
  answered by a separate `POST /answer`. Never a blocking in-request await: an
  SSE connection dying costs nothing.
- The stream closes only on a *terminal* status. Pausing for the learner keeps
  it open with heartbeats, because the session is alive and will emit again.
- `GraphCancelledError`, `GraphTimeoutError`, `BudgetExceededError` and
  `GraphRecursionError` each get their own user-facing message.

---

## 9. Persistence and identity ownership

SQLAlchemy 2.0 async with **Alembic from the first commit** — `alembic check`
reports no drift and downgrade/upgrade round-trips. `create_all` exists only for
the SQLite quick start and tests.

The database contains the existing runtime projections plus identity-owned
learning data: `learners`, `identity_users`, `learner_profiles`, `sessions`,
`run_events`, `mastery`, `misconceptions`, `learning_evidence`,
`learning_preferences`, `learning_events`, `reports`, `agent_tasks`, and
`agent_task_events`. The graph's own checkpointer owns authoritative run state;
LingxiLearn's SQLAlchemy layer owns educational data that must outlive a run.

Protected requests are resolved from a verified `LingxiIdentity.Principal`.
The `(issuer, subject)` mapping is server-owned, and resource queries always
include the mapped internal learner id. Missing and not-owned resources both
return 404. Session completion/failure writes evidence and a learning event in
one idempotent transaction; only normal completion updates mastery,
misconceptions and reports. Existing anonymous guest rows are retained but are
not backfilled into the new identity mapping.

Two rules:

- **Never hold a database session across a graph run.** Resolve, release, then
  stream.
- Checkpoints are namespaced by pack content version
  (`pack/<id>@<version>`), so publishing new lesson content cannot
  reinterpret a session already in flight.

SQLite runs in WAL mode because a background run writes while the API reads.

The web client uses an in-memory bearer-token provider. Since native
`EventSource` cannot attach Authorization headers, SSE is consumed through a
fetch stream while preserving heartbeats and `Last-Event-ID` replay. Agent
artifacts are fetched as authenticated blobs before being opened in an iframe
or downloaded.

---

## 10. Frontend

Next.js 16 / React 19 / Tailwind v4, **statically exported** and served by
FastAPI: one process, one port, no Node in the production image. Nothing needs
server rendering — every byte the learner sees comes from the API at runtime.

The frontend uses the Sim workspace interaction model: a persistent workspace
chrome and sidebar, a streaming-shaped chat lane, and a Resource Panel for the
learning artifact or Agent-produced document. The current application-facing mode
is deterministic local placeholder mode: `web/lib/sim-mock.ts` produces the Sim
conversation, tool, sub-agent, resource and orchestration states without making a
network request. `web/lib/sim-adapter.ts` remains the boundary/reference for a
future LingxiGraph session/agent snapshot and replayable SSE integration. It maps
transcript turns, assistant deltas, plans, tool lifecycle, subagent progress,
evidence and terminal states without changing the backend graph.

The current deep links (`/workspace/?id=<session>` and `/workspace/?task=<agent>`)
remain stable. In placeholder mode they open a local mock run rather than querying
the identifier. The Sim backend, Better Auth, and Sim workspace database are not
used. Modules without a LingxiGraph contract are hidden, explicitly disabled, or
listed in `SIM_LINGXIGRAPH_PLACEHOLDERS.md`.

Domain-specific learning visualizations are intentionally no longer part of the
active frontend tree. They are represented by Sim Resource Panel placeholders until
they can be expressed through Sim's native resource protocol:

| Component | Note |
|---|---|
| `SimResourcePanel` | Sim-style Graph, Artifacts, Sim native capability, and execution-log tabs. Unsupported domain renderers are explicit placeholders. |

The active frontend does not mount the former LingxiLearn conversation, UI,
visualization, or AI-element component families. The Sim-derived shell, composer,
chat message model, resource panel, local placeholder Agent graph, and disabled
capability states are the only application-facing interaction surfaces. The complete
placeholder inventory and the missing LingxiGraph contracts are documented in
`SIM_LINGXIGRAPH_PLACEHOLDERS.md`.

---

## 11. Testing

| Layer | What |
|---|---|
| `pytest` | leak guard, graders, pcap round-trip, simulator determinism, projector mapping, kernel loop with real interrupts, identity ownership and terminal learning idempotency |
| `scripts/smoke.py` | full mission via the real graph, two personas × two missions |

The projector is a pure function specifically so the mapping that drives the
whole UI is testable without a graph, a database or a socket.
