<div align="center">
  <h1>LingxiLearn</h1>
  <p><strong>An AI learning workspace for individual learning tasks</strong></p>
  <p>A continuous system for connecting course content, real tools, agent orchestration, and traceable learning evidence.</p>
  <p>
    <a href="README.md">中文</a>
    ·
    <a href="ARCHITECTURE.md">Architecture</a>
    ·
    <a href="DATA_SOURCES.md">Data sources</a>
    ·
    <a href="LICENSE">MIT License</a>
  </p>
</div>

<table>
  <tr>
    <td><strong>Product form</strong><br />Continuous task-based learning workspace</td>
    <td><strong>Core runtime</strong><br /><code>LingxiGraph 2.2.0</code></td>
    <td><strong>Identity boundary</strong><br /><code>LingxiIdentity</code> BFF</td>
    <td><strong>Deployment</strong><br />Docker Compose</td>
  </tr>
</table>

## Positioning

LingxiLearn is the application layer in the LingXi technology series. It turns learning tasks into executable, verifiable, and traceable workflows. The product boundary is not an open-ended chat surface; it is a complete task loop that receives learning intent, diagnoses the current state, invokes course knowledge and deterministic tools, guides the learner in stages, evaluates mastery, and produces durable evidence and reusable artifacts.

Within the LingXi series, LingxiLearn is the orchestration layer between learning scenarios and shared technical capabilities:

<table>
  <thead>
    <tr>
      <th>Component</th>
      <th>Layer</th>
      <th>Responsibility</th>
      <th>How LingxiLearn uses it</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>LingxiIdentity</strong></td>
      <td>Identity infrastructure</td>
      <td>Authentication, sessions, and subject identity</td>
      <td>Validates identity through the BFF and maintains a same-origin HttpOnly session</td>
    </tr>
    <tr>
      <td><strong>LingxiGraph</strong></td>
      <td>Agent runtime</td>
      <td>State graphs, task orchestration, checkpoints, and runtime extensions</td>
      <td>Hosts the domain-independent learning state machine and Agent Tasks</td>
    </tr>
    <tr>
      <td><strong>LingxiSkills</strong></td>
      <td>Capability catalogue</td>
      <td>Discoverable task capabilities, course tools, and artifact types</td>
      <td>Provides declarative entry points for imports, handouts, checks, and visual explanations</td>
    </tr>
    <tr>
      <td><strong>LingxiLearn</strong></td>
      <td>Scenario application layer</td>
      <td>Learning domain models, course packs, evidence, and the workspace UI</td>
      <td>Composes the shared capabilities into a runnable learning product</td>
    </tr>
  </tbody>
</table>

## Core loop

```text
intake → diagnose → plan → investigate → coach → await_learner
       → judge → advance → verify → report
```

Every node may produce structured state, tool calls, evidence references, or artifact updates. A learner answer is not merely text waiting for a model score: it enters business logic for grading, misconception detection, mastery updates, and evidence accounting. Models primarily provide natural expression and prompt selection; course packs, domain tools, and server-side logic constrain the important decisions.

The first course pack focuses on computer networking, while the teaching kernel remains independent of DNS, TCP, and any single discipline. Adding a course primarily means adding a course pack, knowledge slices, misconception classes, and registered tools—not rewriting the state graph.

## Technical architecture

<table>
  <thead>
    <tr>
      <th>Area</th>
      <th>Implementation</th>
      <th>Boundary</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Web workspace</td>
      <td>Next.js 16, React 19, TypeScript, Tailwind CSS</td>
      <td>Same-origin pages, task conversation, event replay, and artifact rendering</td>
    </tr>
    <tr>
      <td>Application API</td>
      <td>FastAPI, Pydantic, Uvicorn</td>
      <td>Identity-protected Agent Tasks, REST, fetch-SSE, and resource APIs</td>
    </tr>
    <tr>
      <td>Learning data</td>
      <td>SQLAlchemy Async, Alembic, PostgreSQL</td>
      <td>Learner context, mastery, misconceptions, evidence, events, and reports</td>
    </tr>
    <tr>
      <td>Agent runtime</td>
      <td>LingxiGraph StateGraph, checkpoints, and Runtime</td>
      <td>Task state, idempotent progression, resumable execution, and event projection</td>
    </tr>
    <tr>
      <td>Content and tools</td>
      <td>Declarative Course Packs, Tool Registry, and LingxiSkills</td>
      <td>Knowledge sources, deterministic computation, course tasks, and generated artifacts</td>
    </tr>
  </tbody>
</table>

```text
Browser
  │ REST + fetch-SSE
  ▼
Next.js workspace ── LingxiIdentity BFF
  │
  ▼
FastAPI Agent Task API ── LearnerService / SQLAlchemy ── PostgreSQL
  │
  ▼
LingxiGraph StateGraph
  ├── Course Pack
  ├── Tool Registry
  └── safe event / artifact projection
```

The browser reaches the learning API only through the adapter layer under `web/lib/lingxi/`. It receives stage summaries, tool metadata, events, and artifact references—not raw private reasoning or service credentials. In production, the static Next.js output and FastAPI API run in one lightweight application container while PostgreSQL remains a separate service.

## Capability boundaries

- **Course-pack driven**: course content, knowledge slices, prompt ladders, misconception classes, and answer markers are declared in versioned course packs.
- **Real artifact processing**: deterministic tools process pcaps, tables, knowledge bases, and course attachments into verifiable results rather than a single explanatory paragraph.
- **Controlled model adapters**: `scripted`, OpenAI-compatible endpoints, and Coze are supported. `scripted` requires no model key and is suitable for local verification and reproducible evaluation.
- **Traceable results**: task state, tool calls, evidence references, reports, and generated artifacts are linked through REST/SSE and persisted records.
- **Recoverable failure**: task events can be replayed; when an external model is unavailable, the system can fall back to a deterministic path and expose that state explicitly.

The model is not the sole authority for learning outcomes. Grading, misconception detection, mastery, evidence references, and anti-spoiler constraints are owned jointly by the course pack and server-side logic.

## Data and trust boundaries

- Login, registration, and sessions are handled by the `LingxiIdentity` BFF. The browser holds only the HttpOnly `lingxi_session` Cookie and does not persist OIDC/Bearer Tokens locally.
- The server resolves an internal learner mapping from the identity subject returned by the identity service; clients cannot submit an asserted `learner_id`.
- Raw packet bytes, complete tool output, raw database records, and identity information are not sent directly as default teaching context to a model.
- Course materials declare their sources; learning records come from activity, answers, and task interactions in the service. See [DATA_SOURCES.md](DATA_SOURCES.md) for source details.
- LingxiLearn provides learning support and formative feedback. It does not replace a teacher, school, examination, or other professional educational judgment.

## Running locally

### Development

```bash
cp .env.example .env
# Set the database password and identity service configuration.
docker compose -f docker-compose.dev.yml up --build
```

The development frontend is available at `http://localhost:3000`; the API runs at `:8080` inside the Compose network.

### Production

```bash
cp .env.example .env
# Set database, identity BFF, and port configuration.
# Pull latest by default. To pin a release, replace latest in both commands
# with 0.1.0 and set LINGXILEARN_IMAGE_TAG=0.1.0 in .env as well.
docker pull accel.way2api.fun/ghcr.io/lingxi-org/lingxilearn-api:latest
docker pull accel.way2api.fun/ghcr.io/lingxi-org/lingxilearn-web:latest
docker compose pull
docker compose up -d
```

The default production entry point is `http://localhost:8080`. Production Compose pulls API and Web images through `accel.way2api.fun/ghcr.io/lingxi-org` by default. CI publishes both a release tag (currently `0.1.0`) and `latest` for both images; set `LINGXILEARN_IMAGE_TAG` in `.env` to pin a release.

<details>
  <summary>Runtime modes</summary>

| `LINGXILEARN_BRAIN` | Description |
| --- | --- |
| `scripted` | Deterministic engine; no model key required; reproducible results |
| `openai` | OpenAI-compatible endpoint, including OpenAI, DeepSeek, Qwen, Moonshot, vLLM, or Ollama |
| `coze` | Coze Bot integration |

External models participate only in controlled expression and prompt selection. Core learning decisions remain in course logic and the learning data layer.
</details>

## Repository map

```text
packs/<course-pack>/       Course packs, knowledge slices, and misconceptions
server/lingxilearn/        FastAPI, learning services, Agent Tasks, and data layer
skills/                    LingxiSkills capability catalogue
web/                       Next.js workspace and Lingxi API adapter layer
ARCHITECTURE.md            Runtime topology and frontend/backend boundaries
DATA_SOURCES.md            Course data and citation sources
```

## Verification

```bash
make test
cd web
bun run type-check
bun run lint:check
bun run build
```

Deployment details, environment variables, and boundary constraints are defined by the Compose files and the repository documentation: [ARCHITECTURE.md](ARCHITECTURE.md), [Terms of Service](<web/app/(landing)/terms/terms-content.tsx>), and [Privacy Policy](<web/app/(landing)/privacy/privacy-content.tsx>).

## License

This project is released under the [MIT License](LICENSE).
