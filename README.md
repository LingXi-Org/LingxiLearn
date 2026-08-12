# LingxiLearn

**面向高校工科学生的 AI 学习与工程实践助教。**

LingxiLearn 不替你做题。它读懂你当前的状态，调用真实工具处理真实的工程工件，
用问题把你引到结论跟前，验证你是不是真的会了，并把整个过程变成**可回溯的学习证据**。

> 理解学生当前状态 → 调用真实工具/专业知识处理任务 → 启发式交互 → 验证是否真正掌握 → 留下可追溯证据

《计算机网络》是第一个课程包，不是产品边界。教学内核完全不涉及任何具体学科——
数据结构、操作系统、组成原理、嵌入式将来以**内容**的方式加入，而不是重写。

---

## 30 秒跑起来

无需 API Key，无需 Docker，无需数据库。

```bash
make setup     # 安装依赖，生成教学抓包
make dev       # 构建前端 + 启动服务
# 打开 http://localhost:8000
```

一条命令的容器部署：

```bash
cp .env.example .env       # 改一下数据库密码
docker compose up --build  # http://localhost:8080
```

> ⚠️ compose 与 Dockerfile 已完整编写，但**在开发环境中没有 Docker daemon，未经构建验证**。
> 本地 `make dev` 路径是端到端验证过的。

---

## 两个任务，以及它们为什么不能靠对话框完成

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

两个任务走**同一套教学内核**，但调用**完全不相交的工具族**（`net.pcap.*` vs `net.sim.*`）。
课程包与工具注册表的可扩展性是被真实验证过的，不是文档里的承诺。

---

## 它和"AI 聊天"的区别，可以被度量

```
make eval
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
Next.js（中文 UI · 自研 SVG 可视化）
        ↓ Bearer REST + fetch-SSE（可断线续传）
LingxiIdentity OIDC ── FastAPI ── Projector ── run_events（投影日志）
        ↓
LearnerService / SQLAlchemy（学习业务权威源）
        ↓
Tutoring Kernel（LingxiGraph StateGraph · 领域无关）
  intake → diagnose → plan → investigate → coach → await_learner
         → judge → advance → verify → report
        ↓                          ↓
Course Pack（声明式）        Tool Registry（真实确定性计算）
 packs/computer-networks/     net.pcap.* | net.sim.* | net.ipv4.* | kb.*
        ↓
lingxigraph 2.1.0（PyPI）· SQLite / PostgreSQL
```

内核的十个节点没有一个提到 DNS 或 TCP。学科通过**课程包**和**工具注册表**进入，
新增一门课是加一个目录、注册一组工具，不是改图。

细节见 [ARCHITECTURE.md](ARCHITECTURE.md)（英文）。

### 意图调度 Agent 与双 Skill 产物

首页自由 Prompt 会创建一个 Agent Task。意图识别 Agent 先统一教学上下文，随后
`lecture-hook` 与 `visual-explainer` 两个专用 subagent 从同一节点并行扇出，结果在
右侧工作区的“背景文档 / 可视化讲解”标签页汇合。前者输出带来源和不确定性的 Markdown，
后者输出一个零外部依赖的 HTML，并在任务目录内进行静态检查。

新增 Agent 运行时读取以下配置；`DS_API_KEY` 不会进入日志、事件 payload 或 API 响应：

```dotenv
DS_API_KEY=...
LINGXILEARN_AGENT_MODEL=deepseek-v4-flash
LINGXILEARN_AGENT_BASE_URL=https://api.deepseek.com
LINGXILEARN_AGENT_TIMEOUT=90
```

### 身份、学习数据与 LingxiGraph 边界

持久化用户数据接口要求 `Authorization: Bearer <OIDC JWT>`。服务端使用
`LingxiIdentity` 的 `OidcVerifier.verify()` 校验 issuer、audience、签名、过期时间和必需
claims，并只以 `Principal.subject` 查找 `(issuer, subject) → learner` 的内部映射；客户端
不能传入 `learner_id`。生产环境必须配置 OIDC issuer/audience。仅在本地显式设置
`LINGXILEARN_INSECURE_DEV_AUTH=true` 时，缺少 token 的请求才会使用固定的
`LINGXILEARN_DEV_SUBJECT`，不会接受客户端自报身份。

`LearnerProfile`、`Mastery`、`Misconception`、`LearningEvidence`、`LearningPreference`、
`LearningEvent` 以及现有会话/报告表由 LingxiLearn 的 SQLAlchemy/Alembic 数据层负责，
是教育业务的权威源。LingxiGraph 只负责 StateGraph、checkpoint、Runtime，以及可选的
Store/Memory 接缝；graph 运行期间不直接写权威学习表。结果在 session 终态通过一次幂等
事务批量落库。前端只注入内存态 token provider，不把 token 或 learner 缓存在 localStorage；
artifact 与 SSE 使用带 Bearer 的 fetch。

常用用户数据接口：`GET /api/me/context`、`GET /api/me/mastery`、`GET/PATCH
/api/me/preferences`。健康检查、课程包和无持久化 simulator 保持公开。

### 关于 LingxiGraph 与 LingxiNext

LingxiGraph 已发布在 PyPI（`lingxigraph==2.1.0`，核心零运行时依赖），因此这里**直接作为普通
依赖使用**——没有 fork，没有 vendor，没有 submodule。LingxiNext 的工程手法有借鉴
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
make test     # Python 单测 + ruff + mypy + frontend typecheck/test
make eval     # 泄题 / 误区 / 证据 / 学习增益
make smoke    # 需要先起服务：内核 → HTTP+SSE → 真实浏览器
```

`make smoke` 会用 Chromium 真的走一遍两个任务的完整流程——前测、抓包实验室、
带证据钉选的归因表、仿真器操作、后测、可展开引用的学习报告——并在每一步截图到
`var/screenshots/`。

---

## 目录

```
packs/computer-networks/   课程包：概念图、误区分类法、两个任务、知识切片
server/lingxilearn/
  kernel/                  教学内核（领域无关）
  tools/net/               pcap 编解码、抓包分析、可靠传输仿真器
  brains/                  scripted / openai / coze
  stream/                  Event → UI 投影（纯函数）
  store/                   SQLAlchemy + Alembic
  eval/                    评测
skills/                    lecture-hook / visual-explainer（固定上游提交）
web/                       Next.js 前端与自研 SVG 可视化
scripts/                   工件生成、内核/API/UI 冒烟
```

---

## 数据与边界

演示用抓包由 `scripts/build_artifacts.py` 合成，**不含任何真实用户流量**；
学习记录按经 OIDC 验证的 Identity User 映射到服务端内部 learner。旧的匿名 guest 记录
保留在数据库中，但不会自动映射到 Identity 用户，也不会通过受保护 API 暴露。知识库为 RFC 摘录与原创教学笔记，
来源见 [DATA_SOURCES.md](DATA_SOURCES.md)。

> LingxiLearn 用于学习辅导与形成性反馈，**不替代教师、学校或考试的最终评价**。

## 许可

MIT，见 [LICENSE](LICENSE)。
