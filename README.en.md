<div align="center">
  <h1>LingxiLearn</h1>
  <p><strong>AI learning, shaped around you.</strong></p>
  <p>An AI learning workspace for individual learning tasks.</p>
  <p><strong>Everything is a Skill. State decides next.</strong></p>
  <p>
    <a href="README.md">中文</a>
    ·
    <a href="DATA_SOURCES.md">Data Sources</a>
    ·
    <a href="LICENSE">License</a>
  </p>
</div>

## About LingxiLearn

LingxiLearn turns a learning request into a continuous learning task: understand the goal, read the learner state, select the right capabilities, execute them, and decide what to do next from new evidence.

It is not a fixed intent-to-workflow system. The runtime plans in **Capabilities**, then resolves them to concrete Skills and Providers through the Skill Registry.

```text
Goal → Plan → Act → Observe → Update State → Re-plan
```

## Core Experience

- **Visualize** — turn abstract knowledge into diagrams, decks, exercises, and interactive learning artifacts.
- **Understand** — keep goals, mastery, knowledge state, and learning evidence as persistent context.
- **Collaborate** — compose specialist agents dynamically through Skills for explanation, practice, analysis, and feedback.
- **Grow** — update learner state after each round and adapt the next teaching decision.

## Architecture

Production runs separate Next standalone / Node Web, FastAPI API, Python
Scheduler, and PostgreSQL processes. Browser `/api/*` and `/auth/*` requests
stay same-origin through Web rewrites; external LingxiIdentity BFF / Logto owns
identity sessions. See [ARCHITECTURE.md](ARCHITECTURE.md) for topology, startup
order, and ownership.

```text
Browser → Next standalone Web → FastAPI → LingxiGraph
                                  ├→ PostgreSQL / file and artifact storage
                                  └→ LingxiIdentity BFF / Logto
Python Scheduler → PostgreSQL job claims → shared application services
```

Core principle:

> **Everything is a Skill. State decides next.**

Skills define what the system can do. State decides what it should do now.

## Quick Start

### Docker Compose

```bash
cp .env.example .env
# Fill every required credential; missing configuration fails startup

docker compose -f docker-compose.dev.yml up --build
```

Default endpoints:

- Web: `http://localhost:3000`
- API: `http://localhost:8000`

Or simply run:

```bash
make dev
```

### Common Commands

```bash
make setup   # install dependencies
make test    # backend tests
make check   # frontend checks
make prod    # production deployment
```

## Repository Layout

```text
server/     FastAPI backend and learning runtime
web/        Next.js learning workspace
skills/     Skill catalogue
packs/      Course packs and knowledge content
```

Main stack: **Next.js 16 · React 19 · FastAPI · Python 3.13 · LingxiGraph 2.2 · PostgreSQL**

## License

Root project code is released under the [MIT License](LICENSE).

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for historical provenance and third-party notices. The V1 source tree contains none of the retired workspace implementation.
