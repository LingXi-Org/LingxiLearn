# Bundled Agent Skills

This directory contains the two skills used by the intent-driven Agent Task
graph. They are vendored from LingXi-Org/LingxiSkills at commit
`50bc42dacd8b69361aeffb82f630a6ddf9670a4b` and retain the upstream MIT
license and accompanying assets.

- `lecture-hook`: evidence-grounded research and lesson-opening generation.
- `visual-explainer`: single-file, offline interactive HTML explainers.

The backend resolves both directories through LingxiGraph 2.1.0
`FilesystemSkillSource`; generated task artifacts stay under `var/agent_tasks/`
and are intentionally ignored by Git.
