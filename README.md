<div align="center">
  <h1>LingxiLearn</h1>
  <p><strong>AI 学习，因你而变。</strong></p>
  <p>面向个人学习任务的 AI 学习工作台。</p>
  <p><strong>Everything is a Skill. State decides next.</strong></p>
  <p>
    <a href="README.en.md">English</a>
    ·
    <a href="DATA_SOURCES.md">Data Sources</a>
    ·
    <a href="LICENSE">License</a>
  </p>
</div>

## 关于 LingxiLearn

LingxiLearn 将一次学习请求组织为持续运行的学习任务：理解目标、读取学习状态、选择合适的能力执行，并根据新的学习证据动态决定下一步。

它不是固定的「意图 → 工作流」系统。运行时只规划 **Capability**，再由 Skill Registry 解析到具体 Skill 与 Provider。

```text
Goal → Plan → Act → Observe → Update State → Re-plan
```

## 核心体验

- **可视化**：将抽象知识转化为图解、课件、练习与交互式学习产物。
- **理解**：围绕学习目标、知识状态、掌握度与学习证据建立持续上下文。
- **协作**：多个专业 Agent 基于 Skill 动态组合，完成讲解、练习、分析与反馈。
- **成长**：根据每轮学习结果更新状态，并持续调整后续教学策略。

## 架构

生产环境由独立的 Next standalone / Node Web、FastAPI API、Python Scheduler 与 PostgreSQL 组成。浏览器经 Web 的同源 `/api/*`、`/auth/*` rewrite 访问 FastAPI；身份会话由外部 LingxiIdentity BFF / Logto 管理。完整的拓扑、启动顺序与 ownership 见 [ARCHITECTURE.md](ARCHITECTURE.md)。

```text
Browser → Next standalone Web → FastAPI → LingxiGraph
                                  ├→ PostgreSQL / 文件与 Artifact 存储
                                  └→ LingxiIdentity BFF / Logto
Python Scheduler → PostgreSQL 任务声明 → 共享应用服务
```

核心原则：

> **Everything is a Skill. State decides next.**

Skill 定义系统能够做什么，State 决定当前应该做什么。

## 快速开始

### Docker Compose

```bash
cp .env.example .env
# 修改 POSTGRES_PASSWORD

docker compose -f docker-compose.dev.yml up --build
```

默认地址：

- Web: `http://localhost:3000`
- API: `http://localhost:8080`

也可以使用：

```bash
make dev
```

### 常用命令

```bash
make setup   # 安装依赖
make test    # 后端测试
make check   # 前端检查
make prod    # 生产部署
```

合并门禁及其本地复现命令见 [CI 质量门禁](docs/ci-quality-gates.md)。

## 仓库结构

```text
server/     FastAPI 后端与学习运行时
web/        Next.js 学习工作台
skills/     Skill 能力目录
packs/      课程包与知识内容
```

主要技术栈：**Next.js 16 · React 19 · FastAPI · Python 3.13 · LingxiGraph 2.2 · PostgreSQL**

## License

项目根目录代码采用 [MIT License](LICENSE)。

`web/` 中保留部分 Sim 上游 Apache-2.0 代码，许可与来源说明见 [web/SIM_UPSTREAM.md](web/SIM_UPSTREAM.md)。
