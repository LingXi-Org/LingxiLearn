# 数据来源与合规说明

## V1 数据边界

V1 只持久化 Identity 映射、Workspace、AgentTask、Artifact 元数据、Skill
Catalog 元数据和运行健康所需状态。PostgreSQL 是唯一数据库；开发、测试与生产
均必须提供显式 DSN，并通过唯一 Alembic 初始迁移建库。

Artifact 字节写入服务端 `LINGXILEARN_VAR_DIR`。浏览器没有上传入口，也不能直接
访问数据库、文件系统、模型凭据或身份令牌。

## 身份

LingxiIdentity BFF 验证 host-only HttpOnly Cookie。LingxiLearn 只使用验证后的
Principal 建立 Identity 映射；客户端不能提交 learner ID、Bearer Token 或替代
身份头。BFF 地址缺失或不可达时，受保护能力显式失败。

## 课程与 Skill 来源

`packs/` 与 `skills/` 是只读发布输入。正式课程包和 Skill 必须在自身目录声明
引用来源、许可与用途。运行时不会下载缺失内容，也不会用内置示例替代。

## 模型调用

配置的 Provider 可能接收学习目标、对话内容、Skill 指令和必要的学习状态摘要。
身份 Cookie、数据库凭据和内部推理不会发送给 Provider。Provider 选择是精确的；
凭据缺失、调用失败或响应不符合契约时，AgentTask 失败，不切换到本地脚本或另一
Provider。

## 边界声明

LingxiLearn 用于学习辅导与形成性反馈，不替代教师、学校、考试或专业教育机构的
最终评价。
