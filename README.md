<div align="center">
  <h1>LingxiLearn</h1>
  <p><strong>面向个人学习任务的 AI 学习工作台</strong></p>
  <p>将课程内容、真实工具、智能体编排与可追溯学习证据组织成一个连续的学习系统。</p>
  <p>
    <a href="README.en.md">English</a>
    ·
    <a href="ARCHITECTURE.md">架构说明</a>
    ·
    <a href="DATA_SOURCES.md">数据来源</a>
    ·
    <a href="LICENSE">MIT License</a>
  </p>
</div>

<table>
  <tr>
    <td><strong>产品形态</strong><br />连续任务型学习工作台</td>
    <td><strong>核心运行时</strong><br /><code>LingxiGraph 2.2.0</code></td>
    <td><strong>身份边界</strong><br /><code>LingxiIdentity</code> BFF</td>
    <td><strong>部署方式</strong><br />Docker Compose</td>
  </tr>
</table>

## 项目定位

LingxiLearn 是 LingXi 系列技术栈中的应用层项目，负责把学习任务组织成可执行、可验证、可回溯的工作流。它不以开放式问答作为产品边界，而是围绕一个具体任务建立完整闭环：接收学习意图，诊断当前状态，调用课程知识与确定性工具，分阶段引导学习者完成任务，判断掌握情况，并沉淀为学习证据与可复用产物。

在 LingXi 系列中，LingxiLearn 处于“学习场景与技术能力之间的编排层”：

<table>
  <thead>
    <tr>
      <th>组件</th>
      <th>层级</th>
      <th>职责</th>
      <th>LingxiLearn 的使用方式</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>LingxiIdentity</strong></td>
      <td>身份基础设施</td>
      <td>认证、会话和主体身份</td>
      <td>通过 BFF 校验身份，以 HttpOnly Cookie 维持同源会话</td>
    </tr>
    <tr>
      <td><strong>LingxiGraph</strong></td>
      <td>智能体运行时</td>
      <td>状态图、任务编排、检查点和运行时扩展</td>
      <td>承载领域无关的学习任务状态机与 Agent Task</td>
    </tr>
    <tr>
      <td><strong>LingxiSkills</strong></td>
      <td>能力目录</td>
      <td>可发现的任务能力、课程工具和产物类型</td>
      <td>为导入、讲义、检测、可视化等任务提供声明式入口</td>
    </tr>
    <tr>
      <td><strong>LingxiLearn</strong></td>
      <td>场景应用层</td>
      <td>学习领域模型、课程包、证据和交互工作台</td>
      <td>把底层能力组合成可运行的学习产品</td>
    </tr>
  </tbody>
</table>

## 核心闭环

```text
intake → diagnose → plan → investigate → coach → await_learner
       → judge → advance → verify → report
```

每个节点都可以产生结构化状态、工具调用、证据引用或产物更新。学习者的答案不是被动等待模型评价的文本，而是进入判分、误区识别、掌握度更新和证据账本的业务流程。模型主要负责自然表达和提示选择；关键判断由课程包、领域工具和服务端逻辑共同约束。

第一个课程包聚焦《计算机网络》，但教学内核不绑定 DNS、TCP 或任何单一学科。新增课程的主要路径是增加课程包、知识切片、误区分类和工具注册，而不是重写状态图。

## 技术架构

<table>
  <thead>
    <tr>
      <th>区域</th>
      <th>实现</th>
      <th>边界</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Web 工作台</td>
      <td>Next.js 16、React 19、TypeScript、Tailwind CSS</td>
      <td>同源页面、任务对话、事件回放和产物展示</td>
    </tr>
    <tr>
      <td>应用 API</td>
      <td>FastAPI、Pydantic、Uvicorn</td>
      <td>身份保护的 Agent Task、REST、fetch-SSE 和资源接口</td>
    </tr>
    <tr>
      <td>学习数据层</td>
      <td>SQLAlchemy Async、Alembic、PostgreSQL</td>
      <td>学习者上下文、掌握度、误区、证据、事件和报告</td>
    </tr>
    <tr>
      <td>智能体运行时</td>
      <td>LingxiGraph StateGraph、checkpoint、Runtime</td>
      <td>任务状态、幂等推进、可恢复执行和事件投影</td>
    </tr>
    <tr>
      <td>内容与工具</td>
      <td>声明式 Course Pack、Tool Registry、LingxiSkills</td>
      <td>知识来源、确定性计算、课程任务和生成产物</td>
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

前端只通过 `web/lib/lingxi/` 下的适配层访问学习 API。浏览器接收阶段摘要、工具元数据、事件和产物引用，不接收原始私有推理或服务端凭据。生产环境将静态 Next.js 产物与 FastAPI API 放入同一轻量运行容器，PostgreSQL 作为独立服务运行。

## 能力边界

- **课程包驱动**：课程内容、知识片段、提示阶梯、误区分类和答案标记由版本化课程包声明。
- **真实工件处理**：通过确定性工具处理 pcap、表格、知识库和课程附件，输出可核验的结果，而不是只生成一段说明。
- **受控模型接入**：支持 `scripted`、OpenAI 兼容端点和 Coze。`scripted` 模式无需模型密钥，适合本地验证和可复现评测。
- **结果可追溯**：任务状态、工具调用、证据引用、报告和生成产物通过 REST/SSE 与持久化记录关联。
- **失败可恢复**：任务事件支持回放；外部模型不可用时，系统可以降级到确定性路径，并在界面上明确标识。

模型不是学习业务的唯一权威源。判分、误区识别、掌握度、证据引用和防止直接泄题的约束由课程包与服务端逻辑共同负责。

## 数据与信任边界

- 登录、注册和会话由 `LingxiIdentity` BFF 处理；浏览器只持有主域 host-only 的 HttpOnly `__Host-lingxi_session` Cookie，不在本地保存 OIDC/Bearer Token。`/auth/*` 和 `/api/v1/*` 始终通过 LingxiLearn 同源代理。
- 服务端使用身份服务返回的主体映射查找内部学习者，不接受客户端自报的 `learner_id`。
- 原始抓包字节、完整工具输出、数据库原始记录和身份信息不会作为默认教学上下文直接外发给模型。
- 课程资料由课程包声明来源；学习记录来自学习者在本服务中的操作、作答和任务交互。具体来源见 [DATA_SOURCES.md](DATA_SOURCES.md)。
- LingxiLearn 用于学习辅导与形成性反馈，不替代教师、学校、考试或其他专业教育判断。

## 运行方式

### 开发环境

```bash
cp .env.example .env
# 设置数据库密码与身份服务配置
docker compose -f docker-compose.dev.yml up --build
```

开发前端默认访问 `http://localhost:3000`，API 运行在容器内部 `:8080`。

### 生产环境

```bash
cp .env.example .env
# 设置数据库、身份 BFF 和端口配置
# 生产 Compose 始终拉取 main 最新构建的 latest 标签
docker pull accel.way2api.fun/ghcr.io/lingxi-org/lingxilearn-api:latest
docker pull accel.way2api.fun/ghcr.io/lingxi-org/lingxilearn-web:latest
docker compose pull
docker compose up -d
```

默认生产入口为 `http://localhost:8080`。生产 Compose 直接使用 `accel.way2api.fun/ghcr.io/lingxi-org/*:latest`，不会被 `.env` 中的版本变量覆盖。每次 `main` 推送都会为 API 和 Web 生成当前提交的版本标签，并刷新 `latest` 标签。

<details>
  <summary>运行模式</summary>

| `LINGXILEARN_BRAIN` | 说明 |
| --- | --- |
| `scripted` | 确定性引擎，无需模型密钥，结果可复现 |
| `openai` | OpenAI 兼容端点，可接入 OpenAI、DeepSeek、Qwen、Moonshot、vLLM 或 Ollama |
| `coze` | Coze Bot 接入 |

外部模型只参与受控的表达和提示选择；核心学习判断仍由本地课程逻辑和学习数据层负责。
</details>

## 仓库结构

```text
packs/<course-pack>/       课程包、知识切片和误区分类
server/lingxilearn/        FastAPI、学习服务、Agent Task 和数据层
skills/                    LingxiSkills 能力目录
web/                       Next.js 工作台与 Lingxi API 适配层
ARCHITECTURE.md            运行拓扑与前后端边界
DATA_SOURCES.md            课程数据与引用来源
```

## 验证

```bash
make test
cd web
bun run type-check
bun run lint:check
bun run build
```

完整部署说明、环境变量和边界约束以仓库中的 Compose 文件、[ARCHITECTURE.md](ARCHITECTURE.md)、[服务条款](<web/app/(landing)/terms/terms-content.tsx>)与[隐私政策](<web/app/(landing)/privacy/privacy-content.tsx>)为准。

## 许可

本项目采用 [MIT License](LICENSE)。
