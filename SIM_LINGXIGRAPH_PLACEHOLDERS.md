# Sim × LingxiGraph 真实 Agent 工作区

本文件记录当前实现边界。原先用于验证 Sim 交互的本地占位工作区已经移除，前端现在直接消费 LingxiLearn 的 Agent Task REST/SSE 和 Artifact API。

## 用户流程

```text
用户输入问题
      |
      v
POST /api/agent-tasks
      |
      v
recognize_intent
      |
      +--------------------+
      v                    v
lecture_hook       interactive_lecture_deck
      |                    |
      +---------+----------+
                v
          quiz_generator
                |
                v
           await_user
```

后端图定义位于 `server/lingxilearn/agents/graph.py`。意图识别完成后，`lecture_hook` 和 `interactive_lecture_deck` 并行执行，结果交给 `quiz_generator`；任务随后进入 `await_user`。运行事件写入持久化事件表并通过 SSE 回放。`interactive-visual-explainer` 只在对话路由要求时调用。

## 前端数据流

- `/workspace/lingxi/home` 直接创建 Agent Task，然后进入 `/workspace/lingxi/chat/<task-id>`。
- `/workspace/lingxi/w/<task-id>` 使用同一任务快照展示只读工作流。
- `web/hooks/use-agent-task.ts` 读取任务快照并订阅 `/api/agent-tasks/<task-id>/events`。
- `web/lib/lingxi-projection.ts` 将快照和事件转换为聊天消息、活动摘要和 Canvas 图。
- 右侧工作区由 Canvas、课程引入、Lecture deck、结构化 Quiz 和按需 Visual explainer 页面组成。
- Artifact 必须通过 `api.fetchArtifact` 读取，以便携带现有内存鉴权令牌；可视化 HTML 使用受限 iframe 展示。

## Canvas

`web/packages/emcn/workflow-canvas.tsx` 使用 `@xyflow/react` 原生 Canvas，包含：

- User input
- Intent recognizer
- Lecture deck
- Quiz generator
- Handoff placeholder
- Merge results

节点状态由任务快照和 SSE 事件实时推导，连接使用 React Flow Edge，支持原生 Handle、平移、缩放、Controls、MiniMap、网格和自动布局。

## Artifact 页面

| 页面 | Agent | API | 展示方式 |
| --- | --- | --- | --- |
| Lecture deck | `interactive_lecture_deck` | `/api/agent-tasks/{task_id}/artifacts/lecture-deck` | Offline deck + sandboxed iframe |
| Lesson intro | `lecture_hook` | `/api/agent-tasks/{task_id}/artifacts/lesson-intro` | Structured lesson-intro result rendered as a dedicated HTML tab |
| Quiz | `quiz_generator` | `/api/agent-tasks/{task_id}` | Structured JSON rendered by React |
| Visual explainer | on-demand `interactive_visual_explainer` | `/api/agent-tasks/{task_id}/artifacts/visual` | Blob URL + sandboxed iframe |

产物尚未生成时显示等待状态；任务部分失败时保留已成功产物；读取失败时显示错误状态。Blob URL 在页面卸载或任务切换时释放。

## 禁用能力

以下内容不属于当前 Agent 学习链路。它们保留 Sim 风格的页面结构和明确禁用态，
但不产生网络请求或虚假成功状态：

- Files、Tables、Knowledge、Integrations、Scheduled Tasks、Logs、组织和计费写操作
- 本地 `SimMockRun`、mock graph、mock session 和 `localStorage` 资源仓库
- 浏览器本地文件元数据、假 OAuth、假终端、假语音和假工具反馈

Skills、账户偏好、聊天、测验和学习产物是真实接入能力。Sim EE 源码始终排除；
`web/vendor/sim/NOTICE.md` 记录上游 SHA、Apache-2.0 归属和许可边界。

## 验证

```text
cd web
npm run typecheck
npm test
npm run build

cd ../server
pytest -q tests/test_agent_tasks.py
```

本地运行时需要配置 `DS_API_KEY`，并在开发环境启用 `LINGXILEARN_INSECURE_DEV_AUTH=true`；生产环境使用现有 LingxiIdentity OIDC 配置。
