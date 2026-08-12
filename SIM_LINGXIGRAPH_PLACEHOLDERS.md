# Sim 原生能力与 LingxiGraph 对齐占位清单

## 当前状态

当前前端运行在 **Sim native placeholder mode**。首页、工作区、侧栏、输入框、消息流、资源面板和响应式布局均使用 Sim 派生的交互模型；发送消息只在浏览器内生成确定性的占位 Agent 输出，不调用 REST、SSE、LingxiIdentity、数据库、文件系统或外部网络。

入口代码：

- `web/app/page.tsx`：Sim 首页，发送消息后进入占位工作区。
- `web/app/workspace/page.tsx`：Sim 工作区和移动端抽屉/双栏布局。
- `web/lib/sim-mock.ts`：占位消息、工具、子 Agent、资源、编排图和能力目录。
- `web/hooks/use-sim-mock.ts`：本地会话状态，不连接真实 API。
- `web/components/sim/sim-agent-graph.tsx`：占位 Agent 编排图。
- `web/components/sim/sim-resource-panel.tsx`：Graph、Artifacts、Sim native、Run log 四个原生能力面板。

`web/lib/sim-adapter.ts` 仍保留为 LingxiGraph 对接边界和纯函数测试参考，但当前页面不主动使用它，也不产生真实后端请求。

## 已提供的占位能力

资源面板的 **Sim native** 标签会列出全部前端占位能力：

| Sim 能力 | 当前占位表现 | 对齐 LingxiGraph 所需内容 |
|---|---|---|
| Chat conversation / Prompt composer | 本地消息和占位回复 | session transcript、assistant delta、提交/停止协议 |
| Attachments | 禁用入口 | 上传、鉴权、文件生命周期和消息附件事件 |
| Sub-agents | 子 Agent 消息块和状态 | AgentTask snapshot、agent started/completed/failed 事件 |
| Tool calls | 工具卡片和结果状态 | `tool.started`、`tool.completed`、错误与耗时字段 |
| Agent orchestration | 节点、边、执行顺序图 | graph/node 运行状态、依赖关系和可重放事件 |
| Workflows / Skills | 侧栏工作流和能力卡片占位 | workflow/skill 注册、版本和运行 API |
| Browser / Terminal | 明确的 no-op 占位 | 安全沙箱、权限、工具输入输出和审计日志 |
| Resource panel | Sim 原生标签页 | 统一 resource descriptor、预览、下载和生命周期 |
| Files / Tables / Knowledge | Artifact 卡片上的 disabled placeholder | 文件、表格、知识库的后端资源协议与引用 |
| Canvas / visual | Visual explanation 占位卡片 | 可视化 Artifact schema、版本和渲染器 |
| Command search | 未接入入口 | 命令注册、快捷键和 workspace 状态操作 |
| Integrations / Schedules | 未接入入口 | 外部连接配置、定时执行、权限和后台任务 |
| Voice | 未接入入口 | 浏览器媒体权限、转写/合成服务和流式事件 |
| Authentication | `Sign in (placeholder)` | 当前 LingxiIdentity 与 Sim 用户/工作区身份映射 |
| Persistence | 刷新后重新生成本地演示 run | session/task 持久化、历史列表、游标续传 |

## 编排图的占位拓扑

```text
User input
    → Intent router
        → Research agent
            ├─ Knowledge search (no API call)
            ├─ Artifact inspect (no file access)
            └─ Resource panel (placeholder)
```

图中所有节点都标记为 `placeholder` 或 `no API call`。它们用于验证 Sim 原生消息、工具、子 Agent 和资源布局，不代表 LingxiGraph 实际执行过对应节点。

## 与现有 LingxiGraph 的差异

真实实现仍位于后端 FastAPI/LingxiGraph 和对应的 REST/SSE 代码中，主要差异如下：

1. 当前前端没有读取课程包、创建 Session、创建 Agent Task 或提交 learner answer，因此课程流程、测验、报告、mastery 和确定性 Artifact 不会被执行。
2. 当前前端没有打开 SSE 游标、断线重连或事件去重链路；这些能力由 `web/lib/sim-adapter.ts` 和现有 hooks 保留为后续对接参考。
3. 占位 Agent、工具、子 Agent 和资源使用前端固定模型，不具备真实输入校验、权限隔离、失败重试、超时、取消和幂等语义。
4. 深链接 `?id=...` 与 `?task=...` 仍可打开工作区，但只显示 placeholder run，不查询对应的 LingxiGraph 实体。
5. Sim 原生资源类型没有与 LingxiGraph 的 packet ladder、waterfall、simulator、quiz、report 等领域 Artifact 做真实 schema 转换；这些内容统一保留在 Sim Resource Panel 的占位卡片中。
6. Sim 的 Better Auth、workspace database 和真实外部集成没有引入；侧栏身份入口为 disabled/placeholder，避免伪造已登录状态。

## 后续对接顺序

建议先实现统一 resource descriptor 和事件投影，再逐项恢复真实能力：先接 session transcript/SSE，再接 AgentTask/sub-agent，再接工具和 Artifact 资源，最后接文件、知识库、集成、调度、语音和持久化。恢复真实 API 时，应保留当前占位卡片作为无后端能力的降级状态。
