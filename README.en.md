<div align="center">
  <h1>LingxiLearn</h1>
  <p><strong>An AI learning workspace for individual learning tasks</strong></p>
  <p><strong>Everything is a Skill. State decides next.</strong></p>
  <p>Goals, learner state, specialist agents, visual artifacts, and verifiable evidence are coordinated in one continuous learning system.</p>
  <p>
    <a href="README.md">中文</a>
    ·
    <a href="DATA_SOURCES.md">Data sources</a>
    ·
    <a href="web/SIM_UPSTREAM.md">Frontend upstream</a>
    ·
    <a href="LICENSE">License</a>
  </p>
</div>

<table>
  <tr>
    <td><strong>Version</strong><br /><code>2.0.0</code></td>
    <td><strong>Runtime</strong><br /><code>LingxiGraph 2.2.0</code></td>
    <td><strong>Backend</strong><br />FastAPI · Python 3.13</td>
    <td><strong>Frontend</strong><br />Next.js 16 · React 19</td>
  </tr>
</table>

## What LingxiLearn is

LingxiLearn is not an LLM wrapped in a chat box. It turns a learner request into a **plannable, executable, observable, recoverable, and verifiable** learning task.

A learner states what they want to learn, ask, review, or practice. The system interprets that message as a testable goal, generates eligible capabilities from the current learner state, selects Skills and Providers, executes them, observes the outcome, updates state, and then decides again from the new state.

There is no fixed intent-to-workflow routing table in the core runtime:

```text
START → interpret_goal → orchestrate → dispatch → observe
      → update_state → evaluate_goal

evaluate_goal → orchestrate | await_user | END
await_user    → orchestrate
```

**Skills define what the system can do. State decides what should happen now.**

## Product experience

| Direction | Implementation |
| --- | --- |
| **Visualization** | Turns abstract knowledge into lesson intros, decks, diagrams, interactive visuals, exercises, and other learner-facing artifacts. |
| **Understanding** | Maintains goals, knowledge-point state, mastery, misconceptions, questions, and evidence as durable learning context rather than relying only on chat history. |
| **Collaboration** | The orchestrator plans Capabilities; the runtime resolves them through the Skill Registry to concrete Skills and Providers. Independent tasks can share an execution tier when declared parallel-safe. |
| **Growth** | Structured evidence is written back after execution and the next round is planned from the updated profile, closing the learn → feedback → update → re-plan loop. |

## LingxiHarness: the state-driven orchestration kernel

The LingxiLearn control plane can be summarized as **LingxiHarness**. Agent names are not embedded in the topology. Execution is driven by a closed Capability vocabulary, Skill manifests, machine-checkable completion conditions, and learner state.

```text
Learner utterance
      │
      ▼
Goal Interpreter
  “What does the learner want?”
      │
      ▼
World State / Candidate Generation
  profile · evidence · goal · artifacts · cost
      │
      ▼
Orchestrator
  “What is most useful this round?”
      │
      ▼
PlannedTask(capability, done_when, depends_on)
      │
      ▼
Dispatcher
  capability → skill → provider
      │
      ├── Agent Provider
      ├── Deterministic Provider
      └── Tool / Artifact Provider
      │
      ▼
Observe → State Updater → Completion Evaluator
      │
      └──────────────► re-plan / await learner / finish
```

### Goal interpretation is not routing

The Goal Interpreter only answers what the learner wants. It does not emit a route, agent, workflow, or next node. The Orchestrator recomputes the next action every round from the latest state.

### Capabilities are a closed vocabulary

The runtime can only plan registered capability tags such as:

- `model.reflect`, `graph.build`, `graph.prerequisite`, `review.schedule`
- `content.lesson_intro`, `content.deck`, `content.visual`
- `teach.strategy`, `teach.explain`
- `dialog.answer`, `dialog.converse`, `dialog.interview`, `dialog.probe`
- `assess.generate`, `assess.grade`, `assess.interpret`
- `tool.investigate`, `meta.report`, `meta.evaluate`, `meta.author_skill`

Unknown tags are rejected rather than becoming implicit routes.

### Everything is a Skill

`skills/*/SKILL.md` files are the declarative source for the runtime Skill Registry. A manifest may define its capabilities, I/O contracts, preconditions, Provider, cost/latency class, parallel-safety, critical-path status, version, and checksum.

The Orchestrator plans Capabilities instead of binding directly to an Agent. The Dispatcher resolves the concrete Skill and Provider from the registry, so adding a subject, skill, or provider does not require changing the main graph.

### Completion is not “the agent returned”

Every planned task carries a machine-checkable `done_when`. Supported conditions include `artifact_exists`, `artifact_valid`, `evidence_observed`, `profile_reaches`, `user_replied`, `quiz_graded`, `all_of`, and `any_of`.

This prevents a provider from declaring success without producing the intended state change or artifact.

### Shared state is the coordination protocol

Agents coordinate through structured state rather than passing long prose messages between each other:

| State | Purpose |
| --- | --- |
| `learning_profile` | durable learner × knowledge-point state |
| `learning_evidence` | structured observations and learning evidence |
| `session_state` | goal stack, runtime phase, budgets, waiting state |
| `skill_registry` | skills, capabilities, providers, contracts, costs, preconditions |
| `decision_trace` | candidate set, decision, outcome, and state changes per round |

## System architecture

```text
Browser
  │
  ▼
Next.js 16 / React 19 workspace
  │ same-origin REST + replayable SSE
  ▼
FastAPI Agent Task API
  ├── LingxiIdentity session validation
  ├── Workspace / Files / Knowledge / Skills APIs
  ├── Learner profile / Evidence / Artifact APIs
  └── Runtime trace / execution graph projection
  │
  ▼
LingxiHarness V2
  ├── Goal Interpreter
  ├── Candidate Generator
  ├── Orchestrator
  ├── Guardrails
  ├── Dispatcher
  ├── Completion Evaluator
  └── State Updater
  │
  ▼
LingxiGraph 2.2.0
  │
  ├── Skills / Providers / Tools
  ├── Course Packs
  └── PostgreSQL + Artifact Store
```

The browser receives learner-safe stages, status, tool metadata, artifact references, and a projected execution graph. Server credentials and private reasoning are not part of the frontend protocol.

## Frontend workspace and Sim upstream

`web/` is the LingxiLearn product workspace. It retains the non-workflow source closure imported from **Sim v0.8.0 / commit `48c59c8a`**, including workspace chrome, task history, files, tables, knowledge bases, logs, Skills, account pages, and settings. LingxiLearn then connects those surfaces to its FastAPI service and LingxiGraph Agent Task transport.

LingxiLearn **does not run a Sim backend**. Native Workflow Editor/CRUD, deployment, connector management, and realtime collaboration are deliberately removed or disabled. The public `lingxi` workspace slug resolves to the authenticated learner's private workspace.

See [`web/SIM_UPSTREAM.md`](web/SIM_UPSTREAM.md), [`web/LICENSE`](web/LICENSE), and [`web/NOTICE`](web/NOTICE) for the upstream boundary and license notices.

## Identity and data boundary

- Production validates the HttpOnly `lingxi_session` through the LingxiIdentity BFF; the browser does not need to persist a bearer token.
- The server maps the authenticated subject to an internal learner instead of trusting a client-supplied `learner_id`.
- Local development may explicitly enable `LINGXILEARN_INSECURE_DEV_AUTH=true`; production Compose forces the bypass off.
- PostgreSQL is the persistent database in Compose deployments, and Alembic migrations complete before the API starts.
- Private learner data, identity credentials, and server secrets are not exposed as default frontend or model context.

## Models and providers

The repository currently exposes two configurable model layers:

- Tutor Brain: `scripted | openai | coze`. `scripted` supports deterministic local/reproducible verification, `openai` uses an OpenAI-compatible endpoint, and `coze` uses a Coze Bot.
- Agent Task Runtime: `LINGXILEARN_AGENT_MODEL`, `LINGXILEARN_AGENT_BASE_URL`, and `DS_API_KEY` configure the DeepSeek-compatible agent model.

Models can participate in interpretation, planning, generation, and dialogue, while capability allow-lists, state writes, completion predicates, budgets, and critical guardrails remain host-code constraints.

## Quick start

### Requirements

- Docker + Docker Compose
- For host-side development: Python 3.13, `uv`, Bun 1.3.14+, Node.js 22.19+

### Local Compose development

```bash
cp .env.example .env
# At minimum, change POSTGRES_PASSWORD

make dev
# or: docker compose -f docker-compose.dev.yml up --build
```

Default endpoints:

- Web: `http://localhost:3000`
- API: `http://localhost:8080`

The development stack uses source bind mounts, Next dev server, Uvicorn reload, the explicit local auth bypass, and PostgreSQL.

### Production

```bash
cp .env.example .env
# Configure POSTGRES_PASSWORD, LINGXILEARN_IDENTITY_BFF_URL, and model credentials

make prod
```

The default production entrypoint is `http://localhost:8080`.

Current production Compose topology:

```text
postgres
api-var-init → migrate → api
                     └→ scheduler
web → api
```

API and Web images are pulled from the configured accelerated GHCR path using `latest`; the production auth bypass is forced off.

## Development and verification

```bash
make setup   # install backend + frontend dependencies
make test    # backend pytest suite
make check   # frontend TypeScript + Biome checks

cd web && bun run build
```

## Repository layout

```text
LingxiLearn/
├── server/
│   └── lingxilearn/
│       ├── runtime/        # V2 loop / orchestrator / dispatch / guardrails
│       ├── state/          # capabilities / profile / evidence / skill registry
│       ├── agents/         # providers / model runtime / artifact & skill runtime
│       ├── api/            # FastAPI resource and Agent Task APIs
│       └── store/          # persistence repositories
├── skills/                 # SKILL.md capability catalogue
├── packs/                  # declarative course packs and knowledge content
├── web/                    # Next.js learning workspace
├── docker-compose.dev.yml  # bind-mounted local development stack
├── docker-compose.yml      # production web/api/scheduler/postgres stack
├── DATA_SOURCES.md         # content and data provenance
└── VERSION                 # project version
```

## Design principles

> **Everything is a Skill. State decides next.**

1. Keep the runtime graph stable; extend capabilities through data.
2. Plan Capabilities instead of hard-coding Agents into the control graph.
3. Prefer learner state and evidence over raw conversation history.
4. Require verifiable completion predicates instead of model-declared success.
5. Treat observability as part of the product: candidates, decisions, execution, and state changes should be traceable.
6. Separate runtime mechanics from learner experience: surface capability execution without exposing internal control details.

## License

Repository-root code is published under the MIT License in [`LICENSE`](LICENSE).

`web/` also contains Sim-derived Apache-2.0 upstream code and retained notices. Those files remain subject to their original license and notice requirements; see [`web/LICENSE`](web/LICENSE), [`web/NOTICE`](web/NOTICE), and [`web/SIM_UPSTREAM.md`](web/SIM_UPSTREAM.md).
