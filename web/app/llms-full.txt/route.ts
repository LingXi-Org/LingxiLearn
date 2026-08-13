export const dynamic = 'force-static'
export const revalidate = 86400

export function GET() {
  const content = `# 灵犀智学 — LingxiGraph 学习工作台

## 产品概览

灵犀智学面向课程学习任务提供统一的对话工作台。前端只依赖纯 LingxiLearn 后端，通过 REST 创建和查询 Agent Task，通过 SSE 接收任务阶段、思考摘要、工具调用和产物更新。

## 工作流

1. 用户在工作台对话页提交学习目标或上传课程材料。
2. LingxiGraph 创建 Agent Task，并持续发送任务状态和安全化阶段摘要。
3. 前端将消息、思考步骤、工具调用和子任务映射到统一的聊天数据模型。
4. 课程导入、讲义、知识检测、可视化四类结果以 artifact 资源面板展示。

## 产物

### 课程导入

导入课程材料，建立后续学习任务可使用的课程上下文。

### 讲义

将学习内容整理为结构化讲义，并在产物面板中直接阅读。

### 知识检测

以选择题列表呈现检测题目，支持逐题选择、提交和结果反馈。

### 可视化

使用现有知识图谱画布组件展示节点、关系和学习结构。

## 接口边界

- REST：\`/api/agent-tasks\`、任务详情、消息和产物资源
- SSE：\`/api/agent-tasks/{task_id}/events\`
- 认证：LingxiIdentity BFF 的 HttpOnly \`lingxi_session\` Cookie
- 登录入口：\`/login\`、\`/signup\`、\`/reset-password\`

## 页面

- [首页](/)
- [学习工作台](/workspace/lingxi/home/)
- [博客](/blog)
- [知识库](/library)
- [更新日志](/changelog)
`

  return new Response(content, {
    headers: {
      'Content-Type': 'text/markdown; charset=utf-8',
      'Cache-Control': 'public, max-age=86400, s-maxage=86400',
    },
  })
}
