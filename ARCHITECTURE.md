# LingxiLearn architecture

This document describes the current runtime and deployment boundary. It is not
a migration plan. The architecture programme and constraints are tracked in
[issue #36](https://github.com/LingXi-Org/LingxiLearn/issues/36).

## Production topology

```text
Browser
  │ HTTPS, one public origin
  ▼
Next.js standalone Web (Node server.js, :3000)
  │ rewrites /api/* and /auth/*
  ▼
FastAPI (:8000) ───────────────► external LingxiIdentity BFF / Logto
  │                                  auth, session and token owner
  ├──────────────► PostgreSQL
  │                 domain records, events, schedules and resource metadata
  ├──────────────► api-var volume
  │                 workspace file bytes, attachments and artifacts
  └──────────────► LingxiGraph
                    Agent execution/runtime engine

Python scheduler ──► PostgreSQL claims ──► Agent task application services
```

The browser has one origin. Web renders the application and proxies API and
authentication traffic; it is not the LingxiLearn business backend. FastAPI
does **not** serve a static Next export in production. `web/Dockerfile` builds
`.next/standalone/server.js`, and its runtime image starts it with Node.

## Ownership

| Component | Owns | Does not own |
| --- | --- | --- |
| Next.js Web | routes, rendering, browser state, presentation/compatibility adapters, typed HTTP clients, same-origin proxy | LingxiLearn domain persistence, migrations, authorization truth, Agent execution, durable jobs |
| FastAPI | REST/SSE contracts, learner/workspace authorization, application services, repositories, transactions, files/resources, Agent task lifecycle | frontend rendering or issuing identity sessions |
| Python scheduler | durable schedule polling/claiming and scheduled Agent task launch through the shared application services | HTTP presentation or a separate job database |
| LingxiIdentity BFF / Logto | login, identity session, token lifecycle and principal validation | learning/workspace domain data |
| LingxiGraph | Agent graph execution, runtime transitions, interaction pause/resume and provider/tool execution | browser UI or identity sessions |
| PostgreSQL | production domain records, events, schedules, claims, resource metadata and migration state | binary file/artifact payloads |
| `api-var` storage | workspace file bytes, multipart data, task attachments and generated artifact files | authorization or resource metadata |
| `packs/`, `skills/` | read-only course packs and Skill definitions mounted into API/scheduler | mutable learner state |

Rule of thumb: code that decides how data looks or behaves in the browser
belongs in Web. Code that authorizes, validates, persists, schedules or executes
a LingxiLearn domain operation belongs behind a FastAPI application service.
Web may validate a form for feedback, but FastAPI remains authoritative.

## Request and identity path

`web/next.config.ts` rewrites browser requests to `LINGXILEARN_API_ORIGIN`:

- `/api/:path*` → FastAPI `/api/:path*` (REST and SSE);
- `/auth/:path*` → FastAPI `/auth/:path*`.

FastAPI proxies identity `/auth/*` and `/api/v1/*` traffic to the external BFF.
The browser keeps the HttpOnly identity cookie on one origin and never owns the
OIDC exchange or LingxiIdentity bearer/refresh tokens. Production requires
`LINGXILEARN_IDENTITY_BFF_URL` and forces `LINGXILEARN_INSECURE_DEV_AUTH=false`.
The Identity deployment must be reachable for authenticated product traffic.

Development Compose intentionally uses a fixed local learner and does not call
the production Identity BFF. This convenience must never be inherited by a
production deployment.

## Persistence

Production Compose uses PostgreSQL 16. `postgres-data` owns database durability
and Alembic is the schema migration path. File metadata and learner ownership
live in PostgreSQL; bytes live below `LINGXILEARN_VAR_DIR` in `api-var`.
Agent audit files, uploads and generated artifacts live below
`LINGXILEARN_AGENT_TASK_DIR`, also on `api-var`. API and scheduler share the
volume and the read-only `packs/` and `skills/` inputs.

The Python configuration defaults to host-only SQLite at
`var/lingxilearn.sqlite3`. SQLite is not production and does not model
multi-process PostgreSQL locking/concurrency. Both development and production
Compose use PostgreSQL; claims, concurrent workers and migrations must be
verified there.

## Startup, ports and health

Production startup order is encoded in `docker-compose.yml`:

1. PostgreSQL passes `pg_isready`; `api-var-init` prepares filesystem ownership.
2. `migrate` waits for both and runs `alembic upgrade head` to completion.
3. FastAPI and scheduler start after migrations.
4. Web starts after the API image healthcheck succeeds.

Web listens on container port 3000 and is published as
`${LINGXILEARN_WEB_PORT:-8080}`. FastAPI is internal on port 8000. Its image
probes `GET /ready`, which returns HTTP 503 until application services have
initialized and the database responds. `GET /live` checks only that FastAPI can
answer requests. Web probes its own `/ready` rewrite, covering Node plus the
proxy-to-API path. Scheduler has no HTTP server and its inherited image
healthcheck is disabled. LingxiIdentity is external and is not covered by
Compose healthchecks.

Development Compose publishes Web at `localhost:3000` and FastAPI at
`${LINGXILEARN_PORT:-8080}`. It bind-mounts source, but the browser still uses
the same-origin Web rewrite to API port 8000 inside the Compose network.

## Agent and background execution

FastAPI creates and mutates Agent tasks through application services.
LingxiGraph is the execution engine behind the runtime port; the browser only
consumes durable public task events, interactions and artifact/resource
references. Private reasoning and credentials are not public payloads.

The standalone Python scheduler owns scheduled domain work. It claims due
schedules in PostgreSQL and launches Agent tasks through the same composition
root as FastAPI. New durable background capabilities belong in Python
application/repository boundaries, not in a Next route, browser timer or
Web-owned database. See [issue #49](https://github.com/LingXi-Org/LingxiLearn/issues/49).

## Frontend compatibility boundary

Allowed compatibility code is an explicit, narrow adapter for retained data or
an external integration, with an owner and executable deletion condition. It
may translate transport/contracts for presentation, but it must not become a
second domain service, persistence owner, credential/token owner or
authorization source.

Do not add new Next domain APIs, direct Web database access, independent
identity-session fetches, local token storage, Web-owned background jobs,
`@sim/*` packages, fake compatibility routes or restored removed paths.
Historical adapters remain isolated from the native Lingxi path and are not a
template for new work. Related constraints are tracked by
[issue #51](https://github.com/LingXi-Org/LingxiLearn/issues/51) and
[issue #52](https://github.com/LingXi-Org/LingxiLearn/issues/52); enforcement is
documented in [`docs/ci-quality-gates.md`](docs/ci-quality-gates.md).

## Repository map

```text
web/                 Next.js application and Node standalone image
server/lingxilearn/  FastAPI, application services, scheduler and runtime port
server/migrations/   Alembic migrations
packs/               read-only course content
skills/              read-only Skill catalogue
docker-compose.dev.yml   bind-mounted development stack
docker-compose.yml       production Web/API/scheduler/PostgreSQL stack
```

## Verification

```text
cd web
bun run type-check
bun run build

cd ..
docker compose --env-file .env -f docker-compose.dev.yml config
docker compose --env-file .env -f docker-compose.yml config
```

Container CI builds the images and checks that the Web image configuration
contains the Node standalone entrypoint and the declared API/Web healthchecks.
