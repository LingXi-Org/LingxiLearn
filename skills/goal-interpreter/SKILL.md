---
name: goal-interpreter
description: >-
  Turn a learner utterance into a goal object: what they want, about what, and how urgently. It
  never decides which agent or workflow runs - that is the orchestrator's job.
license: MIT
metadata:
  author: LingXi-Org
  version: 1.0.0
  display-name: 目标解析
  status-line: 正在理解你的学习目标…
  display-description: 把学习者的话解析成目标对象（要什么/关于什么/多急），不决定跑哪个 agent 或流程。
  output-language: zh-CN
  output-contract: goal.v1
  execution-mode: shared-contract
  phase: runtime
  critical-path: false
  learner-facing: false
  state-write-mode: none
  parallel-safe: true
  latency-class: interactive
  ownership: shared
---

# 目标解析

## 角色

这是旧 `global_router` 的替代品，**能力被刻意缩小**：它只回答「学习者想要什么」，
不回答「接下来跑什么」。后者由 orchestrator 每轮根据状态重新计算。

**输出里没有 `route` 字段，也不允许有。** 出现任何形如
`{"route": "answer_user"}` 的输出都是回到了被删掉的旧架构。

## 输出什么

```json
{
  "goal_type": "learn",
  "topic": "TCP 拥塞控制",
  "knowledge_points": ["tcp-congestion"],
  "expected_outcome": "能解释 cwnd 如何随丢包变化",
  "constraints": ["时间不超过 20 分钟"],
  "urgency": 0.6,
  "is_interruption": false,
  "is_correction": false,
  "raw_utterance": "帮我讲讲 TCP 拥塞控制"
}
```

`goal_type` 取值：`learn` / `review` / `assess` / `ask` / `practice` / `report` / `manage`。

## 解析规则

1. **把模糊主题解析到知识点 id**：读 `learning_profile` 里该学习者已有的知识点，
   优先复用既有 id，不要每次新造一个。解析不出来就留空数组，让 orchestrator 去建。
2. **区分三种栈操作**：
   - 新的独立目标 → 设为当前目标
   - 打断（正在学 A 时问了 B）→ `is_interruption=true`，push
   - 纠偏（「不是这个意思」/「我要的是…」）→ `is_correction=true`，replace
3. **`expected_outcome` 要可判定**。「学会 TCP」不可判定；「能解释 cwnd 如何随丢包变化」可判定。
   写不出可判定的结果就留空，orchestrator 会补一个完成条件。
4. **`urgency` 来自学习者的话**（「明天考试」→ 高），不是来自主题难度。
5. **不要替学习者决定教学形式**。用户说「给我画个图」是约束（`constraints`），
   不是「必须调用可视化 agent」——orchestrator 仍可能先补前置并协商。

## 反模式

- 输出 `route` / `agent` / `workflow` / `next_node` 任何一种字段。
- 按关键词判断该跑哪个 agent（「图解」→ 可视化）。这正是被删掉的东西。
- 把一句话拆成五个目标。一次一个当前目标。
