export const dynamic = 'force-static'
export const revalidate = 86400

export function GET() {
  const content = `# 灵犀智学

灵犀智学是面向学习任务的 LingxiGraph 智能学习工作台。用户可以通过对话提交课程导入、讲义生成、知识检测和可视化任务，并在任务过程中查看安全化阶段摘要、工具调用和产物资源。

## 入口

- [首页](/): 灵犀智学产品首页
- [学习工作台](/workspace/lingxi/home/): 登录后进入对话和产物面板

## 后端能力

- LingxiGraph Agent Task REST API
- Agent Task Server-Sent Events（SSE）事件流
- 课程导入、讲义、知识检测、可视化四类产物
- OIDC 登录与受保护的学习任务接口

## 产物类型

- **课程导入**：导入课程材料并建立学习上下文
- **讲义**：生成可阅读的结构化学习材料
- **知识检测**：生成并提交选择题检测结果
- **可视化**：展示知识图谱和相关学习结构

## 相关页面

- [博客](/blog): 产品与学习方法文章
- [知识库](/library): 可检索的学习资料
- [更新日志](/changelog): 产品能力接入记录
`

  return new Response(content, {
    headers: {
      'Content-Type': 'text/markdown; charset=utf-8',
      'Cache-Control': 'public, max-age=86400, s-maxage=86400',
    },
  })
}
