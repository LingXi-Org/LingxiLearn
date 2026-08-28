# 贡献指南

感谢你参与 LingxiLearn。提交代码前，请先确认改动属于本仓库负责的学习产品、学习运行时或相关前端能力，并遵守以下约定。

## 开发前必读

- 阅读 [`README.md`](README.md) 了解项目定位与本地启动方式。
- 涉及运行时、数据流、认证、前后端边界或部署方式时，先阅读 [`ARCHITECTURE.md`](ARCHITECTURE.md)。
- 不要把 LingxiLearn 改造成固定的“意图 → 工作流”路由系统。运行时应规划 Capability，并通过 Skill Registry 解析 Skill 与 Provider。

## 仓库边界

```text
server/     FastAPI 后端、学习领域逻辑、认证接入与 LingxiGraph Runtime
web/        Next.js / React 学习工作台
skills/     当前可用 Skill 目录
packs/      课程包与声明式学习内容
contracts/  跨模块数据契约
```

贡献代码时请保持这些边界：

- `web/` 负责界面、交互和浏览器侧数据适配，不应新增第二套 Lingxi 后端或重新引入已经移除的旧 `/api` 领域入口。
- Lingxi 工作区的原生资源通过 `web/lib/api/domains/` 下的领域 client 访问，REST/SSE 统一由 `web/lib/api/transport/` 传输；运行事件通过 LingxiGraph adapter 转换为前端展示结构。
- `server/` 是学习领域和持久化的事实来源。业务状态、学习证据、任务事件和权限判断不得只存在于前端。
- 浏览器认证依赖 HttpOnly session cookie。不要把 bearer token、访问令牌或其他凭据写入 `localStorage`、日志、前端状态或提交内容。
- 不要向前端暴露模型私有推理、密钥、内部凭据或不必要的敏感运行时状态。

## 运行时约束

修改 Orchestrator、Dispatcher、Skill Registry、State 或学习证据逻辑时，必须保持以下原则：

- 图结构保持领域无关；新增学科、Agent 或能力优先通过 Skill、Capability 与数据扩展，而不是在图中增加面向具体意图的固定分支。
- `learning_profile` 只由规定的 profile writer 更新；`learning_evidence` 保持结构化、可追溯并以追加为主。
- 运行时预算、确认、allow-list、重试上限等安全约束应由代码实现，不要仅依赖 prompt。
- 行为变化应同步更新测试；不得删除或弱化用于阻止固定路由回归的测试。
- 数据库结构变化必须提供对应迁移，不要依赖启动时的隐式建表或手工修改生产数据库。

## 开发环境

后端要求 Python 3.13+；前端使用 Bun 1.3.14+，并要求 Node.js 22.19+。

安装当前依赖：

```bash
make setup
```

启动容器化开发环境：

```bash
cp .env.example .env
# 填写本地开发所需配置，不要提交真实密钥
make dev
```

默认开发入口为 Web `http://localhost:3000` 和 API `http://localhost:8080`。

## 提交前检查

至少运行与你改动范围对应的检查。

后端改动：

```bash
make test
```

前端类型和代码规范：

```bash
make check
```

前端逻辑改动应运行相关单元测试：

```bash
cd web
bun run test:unit
```

涉及聊天、运行事件或轨迹投影时，再运行：

```bash
cd web
bun run test:chat
bun run test:trajectory
```

涉及运行时或后端轨迹语义时，应同时运行对应的 `server/tests/` 测试。涉及 Docker、环境变量或部署拓扑时，至少确认开发与生产 Compose 配置可以正常解析。

不要为了让 CI 通过而跳过测试、降低断言、吞掉异常或关闭类型检查。确有必要调整测试或门禁时，应在 PR 中说明对应的行为变化。

## 前端贡献

- 保持现有组件、状态管理和数据访问层级，不要在页面组件中重复实现已有 API client、runtime adapter 或持久化逻辑。
- 不得重新引入已退役的工作台源码、路由或兼容适配；历史归属记录见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。
- 新增依赖前先确认现有依赖无法合理完成需求；避免为单一小功能引入重量级包。
- UI 改动应同时检查桌面端基本可用性、空状态、加载状态、错误状态和长内容场景。

## 数据与安全

- 不提交 `.env`、API Key、Token、Cookie、数据库转储、真实用户学习记录或可识别个人身份的信息。
- 示例数据必须匿名化或使用合成数据。
- 日志和错误信息不得包含凭据、完整认证头或不必要的用户内容。
- 新增外部数据源、模型或服务接入时，应明确失败行为、超时和权限边界。

## 分支、提交与 Pull Request

- 不直接向 `main` 提交功能代码；从最新 `main` 创建独立分支并通过 Pull Request 合并。
- 一个 PR 尽量只解决一个问题，避免把功能、无关重构、格式化和依赖升级混在一起。
- 提交信息建议使用清晰的 Conventional Commit 风格，例如 `feat:`、`fix:`、`docs:`、`test:`、`refactor:`、`chore:`。
- PR 描述应说明用户可观察到的变化、涉及的模块、验证方式，以及是否包含迁移、配置或兼容性影响。
- 行为或接口发生变化时，同步更新对应文档、契约和测试。
- 合并前应确保 required checks 通过，并处理仍然有效的 review conversation。

## 适合提交的贡献

欢迎提交缺陷修复、学习体验改进、可复用 UI、测试、文档、性能优化、可观察性改进以及与现有架构一致的能力扩展。对于会改变核心运行模型、公开接口、持久化语义或安全边界的大型改动，建议先通过 Issue 说明设计和兼容性影响，再开始实现。
