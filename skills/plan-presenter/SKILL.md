---
name: plan-presenter
description: >-
  将已验证的 Runtime 编排计划即时投影为学习者可见的执行计划列表。
metadata:
  version: 1.0.0
  display-name: 执行计划发布
  display-description: 实时更新聊天中的下一步学习计划，不调用模型。
  phase: runtime
  capabilities: plan.present
  provider: plan_presenter
  parallel-safe: true
  critical-path: false
  blocking: false
  latency-class: interactive
  status-line: 正在更新执行计划…
  learner-facing: true
  ownership: dedicated
---

# 执行计划发布

只发布宿主已经验证过的计划项和状态，不重新解释目标，不调用模型，也不改变编排决策。
