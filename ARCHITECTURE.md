# LingxiLearn architecture

LingxiLearn is a learning workspace with one frontend source tree and one
LingxiLearn backend. The frontend keeps the existing product-page and chat-page
design language, while all workspace data comes from LingxiGraph Agent Tasks.

## Repository boundary

```text
web/                 Next.js application; source lives directly at this level
server/lingxilearn/  FastAPI, LingxiIdentity, learning service and REST/SSE API
packs/               Declarative course content
skills/              Current LingxiSkills catalogue
docker-compose.dev.yml   Local development: bind-mounted web + reloadable API
docker-compose.yml       Production: static web build + one API process
```

There is no frontend workspace, package workspace, Turbo project, Sim backend,
Redis service, realtime service, cron service, or Kubernetes deployment in this
repository.

## Runtime topology

### Local development

```text
Browser :3000 ── Next dev server (./web bind-mounted at /app)
                    │
                    └── REST/SSE ── FastAPI :8080 ── PostgreSQL
```

`docker-compose.dev.yml` is the only development deployment. The web container
uses a dedicated `node_modules` and `.next` volume so the host source mount stays
live and Next Fast Refresh sees every change. The API source is also bind-mounted
and runs with reload enabled.

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

The only browser data client is under `web/lib/lingxi/`:

- `api.ts` owns authenticated REST calls and fetch-based SSE.
- `lingxi-graph-adapter.ts` converts LingxiGraph events into the shared chat
  message, reasoning-step, tool-call and subagent shapes.
- `hooks/use-lingxi-chat.ts` owns task creation, task snapshots, event replay and
  message submission.
- `components/lingxi-chat.tsx` renders the workspace conversation.
- `components/lingxi-artifact-resource.tsx` renders course import, handout,
  knowledge check and visualization artifacts with existing UI components.

The frontend never calls a removed Sim `/api` contract and never stores a bearer
token in localStorage. OIDC tokens are held by the in-memory
`LingxiIdentityProvider` and attached to REST/SSE requests.

## Backend data boundary

The FastAPI service owns the LingxiLearn learning domain and exposes:

- OIDC-protected Agent Task REST endpoints;
- replayable Agent Task SSE events;
- skill catalogue and artifact/quiz resource endpoints;
- course packs, learner context, evidence and persistence;
- static frontend fallback in production.

LingxiGraph is used inside the backend task service. The browser receives safe
stage summaries, tool metadata and artifact references rather than raw private
reasoning or credentials.

## Verification

```text
cd web
bun run type-check
bun run build

cd ..
docker compose --env-file .env.example -f docker-compose.dev.yml config
docker compose --env-file .env.example -f docker-compose.yml config
```

For a real local run, copy `.env.example` to `.env`, set the database password
and identity client id, then start the development Compose file. Production uses
the same source tree but serves the static export from the API container.
