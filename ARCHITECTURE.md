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
lingxigraph 2.1.0 (PyPI) · SQLite | PostgreSQL
```

### Intent-driven Agent Tasks

Free-form questions use a separate one-shot graph. `recognize_intent` normalizes
the learner's topic, objective, level and duration, then fans out to
`lecture_hook` and `visual_explainer` in the same graph tick. Both branches are
joined by `merge_results`, so one failed specialist can still leave a `partial`
task with the other artifact available.

The specialists receive LingxiGraph 2.1.0 `FilesystemSkillSource` instances for
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
- a **tool namespace** (`net.pcap.*`, `net.sim.*`, …) registered in the tool
  registry.

Adding 数据结构 or 操作系统 is a new directory plus a new namespace. It is not a
kernel change. The two shipped missions prove this rather than assert it: they
run through the same kernel while calling **disjoint** tool families.

---

## 2. Why LingxiGraph, and how it is used

`lingxigraph` is published on PyPI with **zero required runtime dependencies**,
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

Every tool result, knowledge citation, learner action and simulator outcome
enters an append-only **ledger** with a stable id (`ev_0007`) and a content
digest. Teaching claims and report lines reference those ids; the UI resolves an
id back to a frame, a citation or a simulator step.

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
(simulator flags). No model is asked to speculate about the learner's mind.

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
- `pcapfile.py` — classic libpcap container, with errors phrased for a learner.
- `analysis.py` — flows with Wireshark-style relative sequence numbers,
  retransmission detection, ladder data, and the latency waterfall.
- `synth.py` — the teaching captures. Generated, so ground truth is exact and
  frame numbers are stable across regenerations.
- `sim.py` — the reliable-delivery simulator. Pure functions over a serialisable
  state, with its own LCG so a seed reproduces the same loss pattern on any
  Python version.

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
  (`pack/computer-networks@1.0.0`), so publishing new lesson content cannot
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

The stage is primary; the conversation is a side rail. Inverting that one
relationship is most of what separates this from a chat wrapper.

Visualizations are hand-built SVG with no charting dependency, because the data
is bespoke:

| Component | Note |
|---|---|
| `PacketLadder` | Linear time axis. The long stall is drawn at true scale because that gap *is* the insight; only labels are nudged apart on collision, never the geometry. |
| `LatencyWaterfall` | The learner's answer is the component: split the clock, pin the frames. After grading, their split renders against the parser's on the same axis. |
| `FrameInspector` | Decoded field tree plus hex dump. |
| `SimConsole` | Window strip, sequence-time plot, event log. |
| `RunTrace` / `EvidencePanel` | The audit trail, shown to the learner rather than hidden in a debug console. |

An inversion worth stating: rather than having a model generate interactive HTML
into a sandboxed iframe, LingxiLearn ships hand-built parameterised components
and lets the tutor **select one and fill its props**. This keeps the good idea —
a tutor driving an interactive artefact while explaining it — and drops the
sandbox, the keep-alive pool and the generation variance.

---

## 11. Testing

| Layer | What |
|---|---|
| `pytest` | leak guard, graders, pcap round-trip, simulator determinism, projector mapping, kernel loop with real interrupts, identity ownership and terminal learning idempotency |
| `scripts/smoke.py` | full mission via the real graph, two personas × two missions |
| `scripts/api_smoke.py` | HTTP + SSE, including a deliberate disconnect and `Last-Event-ID` resume, and asserting the answer key never crosses the wire |
| `scripts/ui_smoke.py` | Chromium driving both missions end to end, with screenshots |
| `python -m lingxilearn.eval` | leakage, misconception F1, evidence correctness, learning gain |

The projector is a pure function specifically so the mapping that drives the
whole UI is testable without a graph, a database or a socket.
