# Bundled Agent Skills

This directory contains the current skills loaded from LingXi-Org/LingxiSkills.
The old `lecture-hook` and `visual-explainer` skill names are retired. They are
vendored from LingXi-Org/LingxiSkills at the current upstream commit.
`50bc42dacd8b69361aeffb82f630a6ddf9670a4b` and retain the upstream MIT
license and accompanying assets.

- `lesson-intro`: 课程引入设计。
- `interactive-visual-explainer`: 交互式可视化讲解。
- `adaptive-pedagogy`: 自适应教学。
- `interactive-lecture-deck`: 交互式讲解课件。
- `learner-state-reflector`: 学习状态反思。
- `quiz-generator`: 知识点出题契约骨架（仅定义输入输出规范，尚未实现出题逻辑）。

The backend resolves both directories through LingxiGraph 2.1.0
`FilesystemSkillSource`; generated task artifacts stay under `var/agent_tasks/`
and are intentionally ignored by Git.
