# LingxiLearn architecture

LingxiLearn is a learning workspace with one frontend source tree and one
LingxiLearn backend. The frontend reuses the existing product-page, resource,
and chat UI source, while every Lingxi workspace request terminates at the
canonical FastAPI service.

## Repository boundary

```text
web/                 Next.js application; source lives directly at this level
server/lingxilearn/  FastAPI, LingxiIdentity, learning service and REST/SSE API
packs/               Declarative course content
skills/              Current LingxiSkills catalogue
docker-compose.dev.yml   Local development: bind-mounted web + reloadable API
docker-compose.yml       Production: static web build + one API process
```

There is no separate Sim backend, Redis service, realtime service, or
Kubernetes deployment in this repository. The copied frontend packages are
shared UI/source dependencies; they are not a second Lingxi runtime.

## Runtime topology

### Host development server

```text
Browser :3000 ── Next dev server ── FastAPI :8000 ── var/lingxilearn.sqlite3
```

The host development path reads the root `.env`. Its development identity
switch is explicit, and the SQLite file is the single local database. There is
no `server/var` database.

### Compose development

```text
Browser :3000 ── Next dev server (./web bind-mounted at /app)
                    │
                    └── REST/SSE ── FastAPI :8080 ── PostgreSQL
```

`docker-compose.dev.yml` is the containerized development deployment. The web
container uses dedicated `node_modules` and `.next` volumes, while the API
source and the database schema are bind-mounted. Alembic runs before the API.

### Production

```text
Browser :8080 ── FastAPI ── PostgreSQL
                  │
                  └── /app/web (static Next export)
```

`docker-compose.yml` builds the frontend once into the `web-dist` volume and
serves it from the same lightweight Python process as the API. The runtime image
does not contain Node, Bun, a frontend server, Redis, or a second web process.

## Frontend data boundary

The Lingxi workspace has two explicit browser transport modules, both pointing
to the same FastAPI origin; neither is a Next domain API:

- `web/lib/lingxi/api.ts` owns native Lingxi resources: workspace files/folders,
  agent tasks, settings, skills, and the task SSE stream.
- `web/lib/api/client/request.ts` owns the shared table, knowledge, and log
  contracts used by the reused resource pages.
- `web/lib/lingxi/lingxi-graph-adapter.ts` converts task events into the shared
  chat message, reasoning-step, tool-call, and subagent shapes.
- `web/app/workspace/[workspaceId]/home/hooks/use-lingxi-graph-chat.ts` owns
  task creation, snapshots, event replay, cancellation, and message sending.
- Shared Sim-derived components remain presentation and contract consumers;
  `useChat` has one LingxiGraph transport for the `lingxi` workspace.

For the `lingxi` workspace, credentials, OAuth connections, workflow, and
other unavailable integration surfaces are disabled at the hook boundary, so
they do not probe removed `/api` routes. The browser sends the HttpOnly session
cookie with requests and does not store a bearer token in localStorage.

## Backend data boundary

The FastAPI service owns the LingxiLearn learning domain and exposes:

- OIDC-protected Agent Task REST endpoints;
- replayable Agent Task SSE events;
- the capability registry and artifact/quiz resource endpoints;
- the learning profile, the decision trace and this run's execution graph;
- course packs, learner context, evidence and persistence;
- static frontend fallback in production.

LingxiGraph is used inside the backend task service. The browser receives safe
stage summaries, tool metadata and artifact references rather than raw private
reasoning or credentials.

## The runtime

There is one graph, and nothing in it names an agent or a subject:

```text
START → interpret_goal → orchestrate → dispatch → observe
      → update_state → evaluate_goal
evaluate_goal ──(runtime_status only)──> orchestrate | await_user | END
```

What runs inside `dispatch` is recomputed every round from the learner's state,
resolved `capability tag → skill → provider` through `skill_registry`. Adding a
capability, a skill or a subject changes data; it does not change the graph.

Four tables are the only channel between agents. No agent hands another agent
prose.

| Table | Who writes it | What it holds |
| --- | --- | --- |
| `learning_profile` | `state/profile_writer.py`, and nothing else | one row per learner × knowledge point |
| `learning_evidence` | any provider, append-only | structured observations, never prose |
| `session_state` | the loop | goal stack, run phase, guardrail budget |
| `skill_registry` | startup, from `skills/*/SKILL.md` | capability tags, contracts, preconditions, cost |

`decision_trace` records each round's candidate set, choice, reason, evidence
and profile before/after, and links a replan to what it is redoing.

Guardrails live in `runtime/guardrails.py` and run in code, not in a prompt:
step and replan ceilings, token and time budgets, a capability allow-list, a
heavy-artifact cap, confirmation for irreversible actions, a mandatory
rationale, and a required negotiation sentence before deviating from what the
learner literally asked for.

`server/tests/test_no_fixed_routing.py` fails the build if intent-to-workflow
branching reappears.

## Verification

```text
cd web
bun run type-check
bun run build

cd ..
docker compose --env-file .env -f docker-compose.dev.yml config
docker compose --env-file .env -f docker-compose.yml config
```

For a real local run, copy `.env.example` to `.env`, set the database password
and identity client id, then start the development Compose file. Production uses
the same source tree but serves the static export from the API container.
