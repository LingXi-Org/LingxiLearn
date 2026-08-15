---
name: review-scheduler
description: >-
  Decide which knowledge points are due for retrieval practice and when the next review should
  fall. Use to rank revisiting known material against teaching new material.
license: MIT
metadata:
  author: LingXi-Org
  version: 1.0.0
  display-name: 复习调度
  display-description: 决定哪些知识点该复习、下次复习安排在什么时候，用于和「学新内容」竞争排序。
  output-language: zh-CN
  output-contract: review-schedule-result.v1
  execution-mode: synchronous-structured-generation
  phase: learner-model
  critical-path: false
  learner-facing: false
  state-write-mode: none
  parallel-safe: true
  latency-class: interactive
  capabilities: review.schedule
  status-line: 正在安排复习节奏…
  provider: review_scheduler
  ownership: dedicated
---

# 复习调度

## 角色

遗忘是默认行为，不是意外。这个 skill 让「回头复习」能和「继续学新的」在同一把尺子上比较——
两者都换算成学习收益，由 orchestrator 排序。

## 模型

宿主 `state/scheduling.py` 已实现确定性部分，这里描述它的语义，Skill 不重复计算：

- `stability`：记忆预期还能撑多少天。答对且未用提示 → 按难度决定的 ease 增长；
  答错 → 收缩到原区间的 25%–60%，**不清零**（学习者毕竟见过一次）。
- `review_due_at` = `last_studied_at + stability` 天。
- `review_priority` = `0.45 × 逾期度 + 0.35 × 薄弱度 + 0.20 × 不确定度`，
  存在未消解误区再 `+0.15`，上限 1.0。逾期度按 14 天饱和。

## 这个 Skill 负责什么

1. 从档案里挑出 `review_priority` 最高的 1–3 个点，**不要一次给一张复习清单**。
2. 为每个点说明「为什么现在复习」，引用具体数字（逾期天数 / 掌握度 / 证据条数）。
3. 给出复习形式建议：`retrieval`（无提示回忆）/ `discriminate`（误区辨析）/
   `transfer`（迁移应用）。掌握度低用 `retrieval`，有误区用 `discriminate`，
   掌握度高用 `transfer`。
4. 输出建议的下次 `review_due_at`——只在学习者本轮确实复习了之后才由 state_updater 落库。

## 输出契约 `review-schedule-result.v1`

```json
{
  "due": [
    {"knowledge_point_id": "three-way-handshake", "priority": 0.81,
     "overdue_days": 6, "mastery": 0.44, "evidence_count": 4,
     "form": "discriminate",
     "reason": "逾期 6 天，且上次作答暴露了「SYN 与 ACK 各自计数」的误区"}
  ],
  "not_due": ["tcp-congestion"],
  "warnings": []
}
```

## 反模式

- 一次推 10 个复习点，把控制面板变成待办地狱。
- 只看时间不看掌握度：逾期但已牢固的点不值得挤占本轮。
- 在学习者刚学完的同一轮就安排复习——间隔效应需要间隔。
