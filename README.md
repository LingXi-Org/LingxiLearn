<div align="center">
  <h1>LingxiLearn</h1>
  <p><strong>面向个人学习任务的 AI 学习工作台</strong></p>
  <p><strong>Everything is a Skill. State decides next.</strong></p>
  <p>让学习目标、学习状态、专业 Agent、可视化产物与可验证证据在同一个持续运行的学习系统中协同工作。</p>
  <p>
    <a href="README.en.md">English</a>
    ·
    <a href="DATA_SOURCES.md">数据来源</a>
    ·
    <a href="web/SIM_UPSTREAM.md">前端上游说明</a>
    ·
    <a href="LICENSE">License</a>
  </p>
</div>

<table>
  <tr>
    <td><strong>当前版本</strong><br /><code>2.0.0</code></td>
    <td><strong>核心运行时</strong><br /><code>LingxiGraph 2.2.0</code></td>
    <td><strong>后端</strong><br />FastAPI · Python 3.13</td>
    <td><strong>前端</strong><br />Next.js 16 · React 19</td>
  </tr>
</table>

## 项目定位

LingxiLearn 不是把大模型包装成聊天框，而是把一次学习请求变成一个**可规划、可执行、可观察、可恢复、可验证**的学习任务。

学习者只需要表达“我想学什么 / 问什么 / 练什么”。系统先把自然语言解析为可判定的学习目标，再根据当前学习状态生成候选能力、选择 Skill 与 Provider、执行任务、观察结果、更新学习状态，并在每一轮重新决定下一步。

核心设计不依赖固定的“意图 → 工作流”路由：运行图只描述循环本身，具体运行哪个教学能力由当前状态动态决定。

```text
START → interpret_goal → orchestrate → dispatch → observe
      → update_state → evaluate_goal

evaluate_goal → orchestrate | await_user | END
await_user    → orchestrate
```

**一句话：Skill 决定系统能做什么，State 决定此刻该做什么。**

## 核心体验

| 方向 | LingxiLearn 的实现 |
| --- | --- |
| **可视化** | 将抽象知识转化为课程引入、讲义、图解、可视化页面、练习与其他 Artifact，并在学习工作台中直接呈现。 |
| **理解** | 以学习目标、知识点状态、掌握度、误区、问题与学习证据为持续上下文，而不是只依赖当前聊天窗口。 |
| **协作** | Orchestrator 只规划 Capability，运行时再通过 Skill Registry 解析到实际 Skill 与 Provider；多个互不依赖且声明为并行安全的任务可以进入同一执行层。 |
| **成长** | 每轮执行后把结构化 Evidence 写回学习状态，再根据新的 Profile 重新规划，形成“学习 → 反馈 → 更新 → 再决策”的闭环。 |

## LingxiHarness：状态驱动的学习编排内核

LingxiLearn 的后端控制面可以概括为 **LingxiHarness**。它不把 Agent 名称写进拓扑，而是使用封闭的 Capability 词表、Skill Manifest、完成条件和学习状态驱动执行。

```text
Learner utterance
      │
      ▼
Goal Interpreter
  “学习者想达到什么？”
      │
      ▼
World State / Candidate Generation
  profile · evidence · goal · artifacts · cost
      │
      ▼
Orchestrator
  “这一轮最值得做什么？”
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

### 1. Goal 与 Routing 分离

`Goal Interpreter` 只回答“学习者想要什么”，不会输出 route、agent、workflow 或 next node。真正的下一步由 `Orchestrator` 在每一轮读取最新学习状态后重新计算。

### 2. Capability 是封闭词表

运行时只允许规划注册过的能力，例如：

- `model.reflect`、`graph.build`、`graph.prerequisite`、`review.schedule`
- `content.lesson_intro`、`content.deck`、`content.visual`
- `teach.strategy`、`teach.explain`
- `dialog.answer`、`dialog.converse`、`dialog.interview`、`dialog.probe`
- `assess.generate`、`assess.grade`、`assess.interpret`
- `tool.investigate`、`meta.report`、`meta.evaluate`、`meta.author_skill`

未知 Capability 会被拒绝，而不是悄悄变成新的隐式路由。

### 3. Everything is a Skill

`skills/*/SKILL.md` 是运行时 Skill Registry 的声明源。Manifest 可以声明：

- 提供的 Capability
- 输入 / 输出契约
- 前置条件
- Provider
- 延迟与成本等级
- 是否允许并行
- 是否位于关键路径
- Skill 版本与校验摘要

Orchestrator 规划的是 Capability，不直接绑定 Agent；Dispatcher 再从 Registry 解析具体 Skill 与 Provider，因此新增学科、能力或 Provider 不需要重写主运行图。

### 4. 完成不是“Agent 返回了”

每个 `PlannedTask` 都带有机器可判定的 `done_when`。当前支持的完成条件包括：

`artifact_exists`、`artifact_valid`、`evidence_observed`、`profile_reaches`、`user_replied`、`quiz_graded`、`all_of`、`any_of` 等。

这使系统判断“学到了什么 / 产物是否有效 / 是否需要继续”时，不依赖模型自报完成。

### 5. 学习状态是 Agent 之间的共同协议

运行时围绕结构化状态协作，而不是让多个 Agent 互相转发长篇自然语言：

| 状态 | 作用 |
| --- | --- |
| `learning_profile` | 学习者 × 知识点的持续状态与掌握信息 |
| `learning_evidence` | 作答、工具结果、行为与其他结构化学习证据 |
| `session_state` | 当前 Goal Stack、运行阶段、预算与等待状态 |
| `skill_registry` | Skill、Capability、Provider、契约、成本与前置条件 |
| `decision_trace` | 每轮候选、选择理由、执行结果以及状态变化 |

## 系统架构

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

浏览器只接收可展示的阶段、状态、工具元数据、Artifact 引用和安全的运行图投影；服务端凭据和私有推理不会作为前端协议的一部分返回。

## 前端工作台

`web/` 是 LingxiLearn 的产品工作台。当前工作区保留了从 **Sim v0.8.0 / commit `48c59c8a`** 导入的非 Workflow 源码闭包，包括工作区外壳、任务历史、文件、表格、知识库、日志、Skills、账号与设置等界面，并在其上接入 LingxiLearn 的 FastAPI 与 LingxiGraph Agent Task 传输层。

LingxiLearn **没有运行 Sim 后端**。原生 Workflow Editor / Workflow CRUD / deployment / connector management / realtime collaboration 等能力被明确移除或禁用；`lingxi` 是当前公开工作区 slug，并映射到已认证学习者的私有工作区。

上游边界与许可说明见 [`web/SIM_UPSTREAM.md`](web/SIM_UPSTREAM.md)、[`web/LICENSE`](web/LICENSE) 和 [`web/NOTICE`](web/NOTICE)。

## 身份与数据边界

- 生产环境通过 `LingxiIdentity` BFF 校验 HttpOnly `lingxi_session`；浏览器不需要保存 Bearer Token。
- 服务端从身份主体映射内部 Learner，不接受客户端自行声明的 `learner_id` 作为信任来源。
- 本地开发可显式开启 `LINGXILEARN_INSECURE_DEV_AUTH=true`；生产 Compose 会强制关闭该旁路。
- PostgreSQL 是 Compose 环境的持久化数据库；Alembic migration 在 API 启动前执行。
- 原始学习数据、身份凭据与服务端密钥不会作为默认前端或模型上下文公开。

## 模型与 Provider

仓库保留两类可配置模型入口：

- Tutor Brain：`scripted | openai | coze`。`scripted` 用于确定性、本地和可复现验证；`openai` 使用 OpenAI-compatible API；`coze` 使用 Coze Bot。
- Agent Task Runtime：通过 `LINGXILEARN_AGENT_MODEL` / `LINGXILEARN_AGENT_BASE_URL` / `DS_API_KEY` 配置 DeepSeek-compatible Agent 模型。

模型负责目标理解、规划、内容生成与自然语言交互，但 Capability 白名单、状态写入、完成条件、预算与关键 Guardrail 由宿主代码约束。

## 快速开始

### 前置环境

- Docker + Docker Compose
- 如需宿主机开发：Python 3.13、`uv`、Bun 1.3.14+、Node.js 22.19+

### 本地 Compose 开发

```bash
cp .env.example .env
# 至少修改 POSTGRES_PASSWORD

make dev
# 或：docker compose -f docker-compose.dev.yml up --build
```

默认入口：

- Web：`http://localhost:3000`
- API：`http://localhost:8080`

开发 Compose 使用源码 bind mount、Next dev server、Uvicorn reload、本地开发身份旁路和 PostgreSQL。

### 生产部署

```bash
cp .env.example .env
# 配置 POSTGRES_PASSWORD、LINGXILEARN_IDENTITY_BFF_URL 与模型凭据

make prod
# 等价于先 pull，再 docker compose -f docker-compose.yml up -d
```

默认生产入口为 `http://localhost:8080`。

生产 Compose 当前包含：

```text
postgres
api-var-init → migrate → api
                     └→ scheduler
web → api
```

API 与 Web 默认从加速后的 GHCR `latest` 镜像拉取；生产身份旁路固定关闭。

## 开发与验证

```bash
# 安装依赖
make setup

# 后端测试
make test

# 前端 TypeScript + Biome
make check

# 生产前端构建
cd web && bun run build
```

后端测试目录位于 `server/tests/`，其中包含对固定路由重新出现、运行时契约、状态更新、Agent Task 与其他核心行为的验证。

## 仓库结构

```text
LingxiLearn/
├── server/
│   └── lingxilearn/
│       ├── runtime/        # V2 autonomous loop / orchestrator / dispatch / guardrails
│       ├── state/          # capabilities / profile / evidence / skill registry
│       ├── agents/         # providers / model runtime / artifact & skill runtime
│       ├── api/            # FastAPI resource and Agent Task APIs
│       └── store/          # persistence repositories
├── skills/                 # SKILL.md capability catalogue
├── packs/                  # declarative course packs and knowledge content
├── web/                    # Next.js learning workspace
├── docker-compose.dev.yml  # bind-mounted local development stack
├── docker-compose.yml      # production web/api/scheduler/postgres stack
├── DATA_SOURCES.md         # data and content provenance
└── VERSION                 # project version
```

## 设计原则

> **Everything is a Skill. State decides next.**

1. **运行图保持稳定，能力通过数据扩展。**
2. **规划 Capability，不在控制图中硬编码 Agent。**
3. **学习状态与证据优先于对话历史。**
4. **完成条件必须可验证，而不是依赖模型声明。**
5. **可观测性属于产品：候选、决策、执行与状态变化都应能被追踪。**
6. **运行机制与学习体验分离：前端展示 Capability execution，而不是泄露内部控制细节。**

## License

仓库根目录代码以 [`LICENSE`](LICENSE) 中的 MIT License 发布。

`web/` 中包含从 Sim 导入并继续保留的 Apache-2.0 上游代码与 NOTICE；相关文件继续遵循其原始许可与通知要求，详见 [`web/LICENSE`](web/LICENSE)、[`web/NOTICE`](web/NOTICE) 和 [`web/SIM_UPSTREAM.md`](web/SIM_UPSTREAM.md)。
