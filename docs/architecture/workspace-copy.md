# Workspace 产品文案边界

LingxiLearn 的 Workspace 产品界面固定使用简体中文（`zh-CN`）。当前产品不提供运行时语言切换，因此不引入 i18n 框架或 React Provider；静态文案的唯一事实源是 `web/lib/product-copy`。

## 所有权

- 通用动作、状态、错误、资源列名及 Files、Knowledge、Tables、Logs、Home、Settings、Skills 的界面框架文案属于产品文案 catalog。
- 页面应组合 catalog 文案，不应在多个列表、加载骨架和排序菜单中各自复制列名。
- 动态的 Agent、provider、Skill、MCP 工具名称必须来自服务端契约或注册表的 canonical metadata，不能翻译、猜测或写入 catalog。
- 用户输入、文件名、Agent 生成的学习内容、日志事件名和协议字段属于数据，不是产品文案；必须原样保留。

## 错误边界

UI 只能依据稳定的错误 `code` 或 HTTP `status` 选择产品文案。`Error.message`、响应 `detail`、`rawBody`、堆栈、SQL、内部 URL 等技术信息不得渲染或放入 toast；它们只可进入结构化日志和遥测。

统一入口 `userFacingError(error, fallback)` 同时兼容现有 transport 的错误形态，但有意不读取任何自由文本字段。未知错误必须回退到调用方指定的安全中文文案。

## 变更规则

新增或修改 Workspace 可见文案时：

1. 优先复用 `workspaceCopy` 中已有的语义项。
2. 新增的是跨页面概念时扩展 catalog；只属于单个复杂表单的说明可留在领域组件，但仍须使用中文。
3. 为新的错误 code/status 添加表驱动测试，证明未知技术文本不会泄露。
4. 列表页、加载态、空态和错误态必须使用相同的 catalog 语义。

