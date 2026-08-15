---
name: skill-forge
description: >-
  Draft a new skill manifest when the orchestrator finds no registered capability that can serve
  the goal. The draft is always registered disabled and never auto-enabled.
license: MIT
metadata:
  author: LingXi-Org
  version: 1.0.0
  display-name: 能力起草
  display-description: 当没有任何已注册能力可以服务目标时起草一个新 skill，草稿始终以禁用状态注册，永不自动启用。
  output-language: zh-CN
  output-contract: skill-forge-result.v1
  execution-mode: authoring-structured-generation
  phase: development
  critical-path: false
  learner-facing: false
  state-write-mode: proposal-only
  parallel-safe: true
  latency-class: offline
  capabilities: meta.author_skill
  status-line: 正在起草新的学习能力…
  provider: skill_forge
  ownership: dedicated
---

# 能力起草

## 角色

orchestrator 只能在注册表里选能力。注册表里没有的，它会报一个 `capability_gap`。
这个 skill 把缺口写成一份新的 SKILL.md 草稿。

**草稿永远以 `enabled=false` 注册。** 启用是不可逆操作，必须学习者确认；
每个任务最多起草 `max_forged_skills` 个（默认 1）。

## 起草前先自问

1. **真的缺能力，还是只是候选被前置条件挡住了？** 后者不需要新 skill。
2. **现有 skill 换一组输入能不能覆盖？** 能就不要造新的。
3. **这个缺口会重复出现吗？** 一次性需求不值得一个 skill。

三个问题里有任何一个指向「不需要」，就返回 `{"action": "no_forge", "reason": "..."}`。

## 草稿必须包含

- `name`：kebab-case，动宾结构，说清它做什么
- `metadata.capabilities`：**只能从既有能力词表里选**。词表里没有合适的标签，
  说明这是一次架构变更，不是一个新 skill——返回 `no_forge` 并说明。
- `metadata.provider`：能执行它的 provider；没有现成 provider 时留空，
  草稿只能作为文档存在，不能被调度
- `output-contract`：新契约的名字与字段
- `preconditions`：什么状态下它才可选
- `latency-class` 与是否 `heavy_artifact`
- 正文：角色 / 规则 / 输出契约 / 反模式，与既有 skill 同构

## 输出契约 `skill-forge-result.v1`

```json
{
  "action": "forge",
  "skill_id": "counterexample-generator",
  "manifest": "---\nname: counterexample-generator\n...",
  "capability_gap": "teach.explain 下缺少「用反例暴露误区」这一具体做法",
  "reason": "该学习者连续 3 次在同一误区上失分，正面讲解已重复两轮",
  "enabled": false,
  "requires_confirmation": true
}
```

## 反模式

- 为一次失败起草一个 skill。
- 造一个新的能力标签（那是改架构，不是加技能）。
- 起草完顺手启用。
