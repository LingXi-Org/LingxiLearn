# Bundled Agent Skills

This directory vendors the six skills from `LingXi-Org/LingxiSkills` at upstream
commit `01711cb5ada3df4a4d7dfdc6a8602ba7d335a5c8`.

- `lesson-intro`: 生成可直接打开的单文件中文课程引入 HTML。
- `interactive-visual-explainer`: 生成离线交互式可视化讲解。
- `adaptive-pedagogy`: 根据学习证据选择自适应教学策略。
- `interactive-lecture-deck`: 生成可缩放的离线 HTML 讲解课件。
- `learner-state-reflector`: 反思并压缩学习状态。
- `quiz-generator`: 基于已讲授材料生成 3–4 道有诊断价值的形成性测评，并提供契约校验与公开快照清洗。

`lesson-intro` 的主产物是原始 `lesson-intro.html`，后端直接保存和提供该文件，
不再把结构化结果重新渲染成替代页面。`quiz-generator` 通过 `scripts/quiz_contract.py`
执行输入/结果校验和脱敏；题目由已注册的 skill Agent 实际生成。

后端通过 LingxiGraph `FilesystemSkillSource` 加载这些目录，生成任务产物保存在
`var/agent_tasks/`，并由 Git 忽略。
