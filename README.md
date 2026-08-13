# LingxiLearn

**面向高校工科学生的 AI 学习与工程实践助教。**

LingxiLearn 不替你做题。它读懂你当前的状态，调用真实工具处理真实的工程工件，
用问题把你引到结论跟前，验证你是不是真的会了，并把整个过程变成**可回溯的学习证据**。

> 理解学生当前状态 → 调用真实工具/专业知识处理任务 → 启发式交互 → 验证是否真正掌握 → 留下可追溯证据

《计算机网络》是第一个课程包，不是产品边界。教学内核完全不涉及任何具体学科——
数据结构、操作系统、组成原理、嵌入式将来以**内容**的方式加入，而不是重写。

---

## 30 秒跑起来

本仓库只保留两套 Compose：开发环境绑定本地源码，生产环境把静态前端和
FastAPI 放进同一个轻量运行容器。

```bash
cp .env.example .env       # 设置数据库密码和身份 client id
docker compose -f docker-compose.dev.yml up --build
# 打开 http://localhost:3000
```

生产部署：

```bash
cp .env.example .env       # 改一下数据库密码
docker compose up --build  # http://localhost:8080
```

### Docker 国内源与 `.env` 配置

Compose 默认使用以下国内源：阿里云容器镜像、清华 PyPI、npmmirror npm、阿里云 Debian。需要更换镜像站时，只改 `.env` 中这四项即可：

```dotenv
DOCKER_REGISTRY=docker.m.daocloud.io
PYPI_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
NPM_REGISTRY=https://registry.npmmirror.com
APT_MIRROR=mirrors.aliyun.com
```

首次部署建议至少填写：

```dotenv
POSTGRES_PASSWORD=请改成随机强密码
LINGXILEARN_PORT=8080
LINGXILEARN_BRAIN=scripted
DS_API_KEY=你的 DeepSeek API Key        # 使用 Agent Task 时填写；不使用可留空
```

`scripted` 模式不需要任何大模型 Key，可以直接启动。若使用 OpenAI 兼容模型，将以下三项改成对应服务商配置：

```dotenv
LINGXILEARN_BRAIN=openai
LINGXILEARN_LLM_MODEL=模型名
LINGXILEARN_LLM_BASE_URL=https://兼容接口地址/v1
LINGXILEARN_LLM_API_KEY=API Key
```

开发 Compose 的前端地址是 `http://localhost:3000`，生产 Compose 的同源地址是
`http://localhost:8080`。登录、注册和找回密码由同源 LingxiIdentity BFF 发起，浏览器只持有
HttpOnly `lingxi_session` Cookie，不保存 OIDC/Bearer token。生产环境必须关闭开发免认证，并填写 BFF 地址：

```dotenv
LINGXILEARN_INSECURE_DEV_AUTH=false
LINGXILEARN_IDENTITY_BFF_URL=http://identity-bff:8080
LINGXILEARN_IDENTITY_BFF_TIMEOUT=10
```

Identity BFF 与 LingxiLearn 共域或由反向代理暴露 `/auth/*`、`/api/v1/*` 时无需额外浏览器配置；
本地 Next 开发可将 `NEXT_PUBLIC_API_BASE` 指向 `http://localhost:8080`。

修改 `.env` 后执行：

```bash
docker compose config
docker compose up -d --build
```

> ⚠️ 本地 `make dev` 路径是端到端验证过的；Docker 构建是否成功还取决于服务器能否访问所选镜像站和包源。

---

## 课程任务，以及它们为什么不能靠对话框完成

判断标准很简单：**把题干贴进 ChatGPT 就能解决的任务，一律不做。**

### 慢在哪一环 · 分析真实工件

学生拿到一份**真实的二进制 pcap**（我们逐字节合成，可以直接用 Wireshark 打开核对）。
产出不是一段回答，而是一张**时延归因表**：把这次加载的墙钟时间拆到 DNS 解析 / TCP 建连 /
请求等待 / 数据传输 / 重传停顿五个环节，**并为每一环钉上作为依据的帧**。

判定完全确定性，而且是两道独立的关：

1. 每个桶的量级是否落在解析器算出的基准容差内；
2. 钉的每一帧是否真的存在、是否真的承担所声称的角色。

**数字对了但帧钉错了，不通过**——工程结论的分量来自证据本身。

误区从「质量分到了哪个桶」反推：把重传停顿算成服务器慢 → `transfer_time_as_server_think`；
算进 DNS → `rtx_vs_resolution_confusion`。

这份抓包有个刻意设计的教学点：**最大的一块时间不是服务器处理（188.6 ms），而是一次丢包
引发的停顿（225.8 ms）**。凭直觉答"服务器慢"的人会错得很有意思。

### 你来当发送方 · 在动态系统中承担角色

学生就是 TCP 的发送方，面对一个**带种子的确定性网络仿真器**。每个决策点由他决定
下一步做什么（发下一段 / 重传某段 / 重传整窗 / 什么都不做），仿真器立刻把后果算出来。

判定同样是跑出来的：接收方拿到的字节流是否完整无误，以及吞吐相对 oracle 发送方的比值。
误区从**决策模式**反推——收到三个重复 ACK 不快重传、超时即重传整窗、重传已被累计确认的段。

**这里没有可以背下来的答案。** 正确动作取决于此刻的窗口、在途段和刚收到的确认，
而系统会对你的每一个决定做出反应。一个会还手的系统，是对话框给不了的。

正式课程任务将通过课程包提供，并复用同一套教学内核和工具注册表。

---

## 它和"AI 聊天"的区别，可以被度量

```
make test
```

| 指标 | 结果 | 怎么测的 |
|---|---:|---|
| 泄题率 | **0.000** | 每个步骤 × 每一级提示 × 4 句「直接告诉我答案」的对抗性追问，共 120 个教练回合 |
| 误区识别 macro-F1 | **1.000** | 37 个带标注的错误答案，覆盖 11 类误区；用例由课程包直接生成，不会与内容脱节 |
| 证据正确率 | **1.000** | 58 条引用：证据帧是否存在、帧角色是否属实、文案里点名的帧号是否真实、知识检索是否取得到 |
| 学习增益 | **+100%** | 合成学习者的**流程验证**，不代表真实学生效果 |

泄题率能被度量，是因为**防泄题是程序状态而不是提示词**：每个步骤在课程包里声明自己的
答案标记，每一句教练输出在送到学生面前之前都要过一遍守卫（NFKC 折叠 + 标点归一，
中文没有词边界也拦得住）。守卫命中就降级成课程作者写的提示，无论哪个模型生成的都一样。

---

## 架构

```
Next.js（Sim 全站信息架构 · Lingxi 品牌）
        ↓ REST + fetch-SSE（鉴权、去重、可断线续传）
LingxiIdentity BFF ── FastAPI ── Projector ── run_events（投影日志）
        ↓
LearnerService / SQLAlchemy（学习业务权威源）
        ↓
Tutoring Kernel（LingxiGraph StateGraph · 领域无关）
  intake → diagnose → plan → investigate → coach → await_learner
         → judge → advance → verify → report
        ↓                          ↓
Course Pack（声明式）        Tool Registry（真实确定性计算）
 packs/<course-pack>/         course-specific tools | kb.*
        ↓
lingxigraph 2.2.0（PyPI）· SQLite / PostgreSQL
```

内核的十个节点没有一个提到 DNS 或 TCP。学科通过**课程包**和**工具注册表**进入，
新增一门课是加一个目录、注册一组工具，不是改图。

细节见 [ARCHITECTURE.md](ARCHITECTURE.md)（英文）。

### 意图调度 Agent 与双 Skill 产物

首页自由 Prompt 会创建一个 Agent Task。意图识别 Agent 先统一教学上下文，随后
`lesson-intro` 与 `interactive-lecture-deck` 从同一节点并行扇出，结果交给稳定契约的
`quiz_generator` 生成结构化题目。任务暂停等待学习者对话或一次性答题；按需的
`interactive-visual-explainer` 会在右侧打开独立讲解页面，完成或放弃答题后 handoff 回主图。

新增 Agent 运行时读取以下配置；`DS_API_KEY` 不会进入日志、事件 payload 或 API 响应：

```dotenv
DS_API_KEY=...
LINGXILEARN_AGENT_MODEL=deepseek-v4-flash
LINGXILEARN_AGENT_BASE_URL=https://api.deepseek.com
LINGXILEARN_AGENT_TIMEOUT=90
```

当 Agent Base URL 为官方 DeepSeek API 时，`lesson-intro` 使用 DeepSeek
Responses API 的原生 `web_search` 工具；不再依赖本地 DuckDuckGo HTML 搜索器。

### 身份、学习数据与 LingxiGraph 边界

持久化用户数据接口使用 LingxiIdentity BFF 的 HttpOnly `lingxi_session` Cookie。服务端把
Cookie 转发到 BFF 的 `GET /api/v1/me`，只以返回的 `Principal.subject` 查找
`(issuer, subject) → learner` 的内部映射；客户端不能传入 `learner_id`，也不会保存或发送
LingxiIdentity Bearer token。仅在本地显式设置 `LINGXILEARN_INSECURE_DEV_AUTH=true` 时，
缺少会话的请求才会使用固定的 `LINGXILEARN_DEV_SUBJECT`，不会接受客户端自报身份。

`LearnerProfile`、`Mastery`、`Misconception`、`LearningEvidence`、`LearningPreference`、
`LearningEvent` 以及现有会话/报告表由 LingxiLearn 的 SQLAlchemy/Alembic 数据层负责，
是教育业务的权威源。LingxiGraph 只负责 StateGraph、checkpoint、Runtime，以及可选的
Store/Memory 接缝；graph 运行期间不直接写权威学习表。结果在 session 终态通过一次幂等
事务批量落库。artifact 与 SSE 和普通 API 请求一样使用 HttpOnly Cookie。

常用用户数据接口：`GET /api/me/context`、`GET /api/me/mastery`、`GET/PATCH
/api/me/preferences`。健康检查和课程包接口保持公开。

### 关于 LingxiGraph 与 LingxiNext

LingxiGraph 已发布在 PyPI（`lingxigraph==2.2.0`，核心零运行时依赖），因此这里**直接作为普通
依赖使用**——没有 fork，没有 vendor，没有 submodule。LingxiLearn 的 Agent Task 现在按
Agent 角色复用稳定前缀的模型实例，并启用 LingxiGraph 2.2.0 的 cache-first 投影，让
DeepSeek 原生 prompt cache 不会被不同 system prompt/tool schema 互相污染。LingxiNext 的工程手法有借鉴
（用内容版本做 checkpoint 命名空间、compose 的迁移闸门、两阶段 uv 镜像），
但代码是独立的。三个参考项目都在 `.gitignore` 中，不进入本仓库。

---

## 教练引擎：三选一，缺 Key 自动降级

| `LINGXILEARN_BRAIN` | 说明 |
|---|---|
| `scripted`（默认） | 确定性引擎。无需 Key、无需网络、结果可复现 |
| `openai` | 任何 OpenAI 兼容端点（OpenAI / DeepSeek / Qwen / Moonshot / vLLM / Ollama） |
| `coze` | Coze Bot |

**为什么没有 Key 也能跑完整闭环**：决定教学质量的部分——判分、误区识别、掌握度、
证据账本、防泄题——本来就是确定性的。模型只做一件事：从课程作者写好的问题、提示阶梯和
针对性追问里挑一条，把它说得自然些。所以三种引擎在教学上是等价的，只是措辞不同。

选了 `openai`/`coze` 但没填凭据时，系统降级到 `scripted` 并在界面上明确标注，
而不是在教学中途失败。

> 本次交付中，`openai` 与 `coze` 两个 provider 的代码与配置齐备，
> 但开发环境没有任何 LLM API Key，**未经真实凭据联调**。

---

## 验证方式

```bash
make test              # 后端单测、lint、类型检查 + 前端检查
cd web && npm run verify # 许可证边界、TypeScript、Vitest、静态生产构建
```

当前前端保留既有产品页和网页对话页的设计语言，同时直接连接 Lingxi Agent
Task REST/SSE。正式入口为 `/workspace/lingxi/home/`，对话页为
`/workspace/lingxi/chat/{taskId}/`。课程导入、讲义、知识检测和可视化产物由
统一资源面板展示；未接入的产品模块只保留明确的静态能力说明，不调用不存在的 API。


---

## 目录

```
packs/<course-pack>/      课程包：概念图、误区分类法、知识切片
server/lingxilearn/
  kernel/                  教学内核（领域无关）
  tools/net/               pcap 编解码、抓包分析、可靠传输仿真器
  brains/                  scripted / openai / coze
  stream/                  Event → UI 投影（纯函数）
  store/                   SQLAlchemy + Alembic
  eval/                    评测
skills/                    LingxiSkills 最新技能（含中文展示名称与描述）
web/                       直接位于根目录的 Next.js 前端与 Lingxi API 适配层
```

---

## 数据与边界

课程数据由课程包声明，**不含任何真实用户流量**；
学习记录按经 LingxiIdentity BFF 验证的 Identity User 映射到服务端内部 learner。旧的匿名 guest 记录
保留在数据库中，但不会自动映射到 Identity 用户，也不会通过受保护 API 暴露。知识库为 RFC 摘录与原创教学笔记，
来源见 [DATA_SOURCES.md](DATA_SOURCES.md)。

> LingxiLearn 用于学习辅导与形成性反馈，**不替代教师、学校或考试的最终评价**。

## 许可

MIT，见 [LICENSE](LICENSE)。
