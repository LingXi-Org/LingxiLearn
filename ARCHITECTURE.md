# LingxiLearn V1 architecture

This document is the contract for the clean V1 baseline. The release contains
only Identity, Workspace, AgentTask, Artifact, Skill Catalog, and Health.

## Production topology

```text
Browser
  │ one public origin
  ▼
Next.js standalone Web (:3000)
  │ same-origin /api/* and /auth/* rewrites
  ▼
FastAPI (:8000) ───────────────► LingxiIdentity BFF
  │
  ├──────────────► PostgreSQL 16
  ├──────────────► api-var Artifact storage
  └──────────────► LingxiGraph AgentTask runtime

Python scheduler ──► PostgreSQL claims ──► AgentTask application service
```

The Web process owns rendering and the same-origin proxy. FastAPI owns domain
authorization, validation, transactions, AgentTask execution, and the public
REST/SSE contracts. LingxiIdentity owns login and identity cookies. PostgreSQL
is the only database.

## Public capabilities

- Identity: `/auth/*` and `/api/v1/me`, proxied to LingxiIdentity.
- Workspace: `/api/workspaces`.
- AgentTask: task lifecycle, durable events, interactions, runtime views, and
  scheduling below `/api/workspaces/{workspace_id}/agent-tasks`.
- Artifact: `/api/workspaces/{workspace_id}/artifacts`.
- Skill Catalog: `/api/skills` and `/api/skill-registry`.
- Health: `/live` and `/ready`.

No SQLite, browser-owned domain API, static SPA export, compatibility route,
or alternate API base exists in this baseline.

## Persistence and startup

`server/migrations/versions/0001_initial_schema.py` is the only migration.
Every environment starts from PostgreSQL and runs `alembic upgrade head`; the
application never calls `create_all` or repairs schemas at runtime. Artifact
bytes live in `api-var`; domain metadata and migration state live in
PostgreSQL. `packs/` and `skills/` are read-only runtime inputs.

Production startup is ordered as follows:

1. PostgreSQL becomes healthy and `api-var-init` establishes storage ownership.
2. `migrate` applies the single migration.
3. API and scheduler start only after migration success.
4. Web starts after API readiness.

`/live` proves the API process can answer. `/ready` proves application startup
and database access. Missing database, Identity, model, checkpoint, or signing
configuration fails startup instead of selecting a substitute.

## Release identity

Production Compose accepts only immutable images tagged
`sha-${LINGXILEARN_RELEASE_SHA}`. API and Web therefore run the same source SHA;
the release SHA is also embedded in OCI image metadata. Empty or mutable image
tags are not supported.

## Source boundaries

Backend HTTP modules depend on application ports and contracts, not SQLAlchemy,
repositories, or filesystem paths. The composition root supplies PostgreSQL,
Artifact storage, Identity, Skill Catalog, and AgentTask runtime adapters.

Frontend dependencies flow in one direction:

```text
app → features → entities → shared
```

`web/shared/api/client.ts` is the only HTTP client. Types in
`web/shared/api/generated/schema.ts` are generated from `server/openapi.json`.

## Verification

```text
cd server
uv run python scripts/check_architecture.py
uv run python scripts/export_openapi.py --check
uv run ruff check lingxilearn tests scripts
uv run ruff format --check lingxilearn tests scripts

cd ../web
bun run generate:api
bun run check
bun run build
```

The backend architecture gate rejects unreachable production modules, removed
capability tokens, boundary violations, and any migration count other than one.
The frontend gate checks types, formatting, tests, unused production code, and
dependency direction.

## Repository map

```text
server/                 FastAPI, application services, scheduler, runtime
server/migrations/      the PostgreSQL V1 initial migration
web/                    Next.js V1 product surface
skills/                 read-only Skill definitions
packs/                  read-only course/runtime content
docker-compose.yml      immutable-SHA production deployment
docker-compose.dev.yml  bind-mounted PostgreSQL development deployment
```
