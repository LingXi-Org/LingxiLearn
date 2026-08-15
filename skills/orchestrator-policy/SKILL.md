---
name: orchestrator-policy
description: >-
  Evaluate learning utility and choose the next actions in one model decision. The contract keeps
  utility evaluation and plan orchestration as two separately auditable skills while exposing one
  fast runtime control node.
license: MIT
metadata:
  author: LingXi-Org
  version: 1.0.0
  display-name: 学习计划决策
  status-line: 正在评估学习效用并生成下一步计划…
  display-description: 在一个极速模型节点中分别完成学习效用评估与学习计划编排；保留两个可审计技能语义，只谈能力，不谈 agent 名。
  output-language: zh-CN
  output-contract: orchestration-plan.v1
  execution-mode: shared-contract
  phase: runtime
  critical-path: false
  learner-facing: false
  state-write-mode: none
  parallel-safe: true
  latency-class: interactive
  ownership: shared
---

# 学习计划决策

本技能由两个独立、可审计的子技能组成，但在 Runtime Loop 中使用一次模型调用完成：

1. **学习效用评估**：逐项输出 `gain`、`utility` 和中文理由，体现学习收益与成本权衡。
2. **学习计划编排**：使用上述评分选择任务、判断真实依赖并生成分层计划。

两者不得拆成串行模型调用。候选任务没有真实数据依赖时，`depends_on` 必须为空，
让运行时把它们放入同一层并行执行。

## 角色

每一轮重新决策，而不是一次性分流。这个 skill 描述 orchestrator 在拿到
**已由宿主确定性打分的候选集**之后要做什么。

宿主已经算好了 `expected_learning_gain / cost`。模型的工作是**在这个受限列表里挑选和排序**，
并说明理由——不是自己发明动作。列表之外的能力一律不可选。

## 你会拿到什么

```json
{
  "goal": { "...goal.v1..." },
  "profile": { "target": {...}, "prerequisites": [...], "due_for_review": [...] },
  "budget": {"steps_used": 3, "max_steps": 24, "replans_used": 1, "max_replans": 6,
             "heavy_artifacts_used": 1, "max_heavy_artifacts": 6},
  "candidates": [
    {"capability": "graph.prerequisite", "utility": 0.72, "gain": 0.55, "cost": 0.76,
     "reason": "尚未分析该知识点的前置依赖", "skill_id": "prerequisite-analyzer"},
    {"capability": "content.deck", "utility": 0.31, "gain": 0.62, "cost": 2.0,
     "reason": "缺少系统讲解材料", "skill_id": "interactive-lecture-deck"}
  ]
}
```

## 你要输出什么 `orchestration-plan.v1`

```json
{
  "reasoning": "判断理由，一到三句",
  "hypotheses": ["当前假设，例如：学习者卡在窗口概念而不是公式"],
  "tasks": [
    {"id": "t1", "capability": "graph.prerequisite", "inputs": {},
     "depends_on": [],
     "done_when": {"kind": "evidence_observed", "signal": "error_pattern"},
     "rationale": "可展示给学习者的一句话",
     "expected_learning_gain": 0.55}
  ],
  "goal_satisfied_when": {"kind": "profile_reaches",
                          "knowledge_point_id": "tcp-congestion", "mastery": 0.7},
  "awaits_user": false,
  "negotiation": null
}
```

## 规则

1. **一轮最多 6 个任务**。计划长了就不是计划，是猜测；未达成会重规划。
2. **每个任务必须有 `done_when`，而且必须可机器判定**。
   「agent 跑完」不是完成条件。可用类型：`artifact_exists` / `artifact_valid` /
   `evidence_observed` / `profile_reaches` / `user_replied` / `quiz_graded` /
   `all_of` / `any_of`。
3. **每个任务必须有 `rationale`，且要能直接展示给学习者**。空 rationale 的计划会被护栏拒绝。
4. **偏离用户字面要求时必须写 `negotiation` 并置 `awaits_user=true`**。
   护栏会拒绝「偏离但没协商」的计划。
5. **不要为了用满预算而加任务**。剩余步数不是必须花掉的。
6. **同一知识点的相关产物应在同一轮一起下发**；彼此无真实数据依赖时 `depends_on` 必须为空。
7. 输出 `holds` 与 `delivery_order`；`delivery_order` 是学生学习顺序，不是生成顺序。
7. **不要写 agent 名**。`capability` 是唯一的选择维度；谁来执行由注册表在运行时解析。

## 排序直觉

宿主的 utility 已经编码了主要规则（前置未满足优先补前置、证据太薄优先测、
产物缺失优先生成、逾期高优先复习）。你可以在下面两种情况下偏离 argmax，**并说明原因**：

- 候选之间 utility 差距 < 0.05 时，选对学习者当下更连贯的那个。
- 学习者刚明确拒绝过某个方向时，即使 utility 最高也跳过它。

其它情况请跟随打分。**不要用「我觉得先讲概念更自然」覆盖有数据支撑的排序。**

## 反模式

- 输出一个固定的四步流程（引入 → 课件 → 出题 → 讲解），不管档案是什么样。
- 选择列表之外的能力。
- `done_when` 写成散文（「直到学生理解为止」）。
- 一轮塞 6 个任务然后指望重规划来收拾。
