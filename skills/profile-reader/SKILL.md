---
name: profile-reader
description: >-
  Read a learner's learning_profile rows and project them into the compact view a teaching or
  planning step actually needs. Use before any decision that depends on what the learner already
  knows; never use it to write the profile.
license: MIT
metadata:
  author: LingXi-Org
  version: 1.0.0
  display-name: 学习档案读取
  status-line: 正在读取你的学习档案…
  display-description: 把 learning_profile 投影成教学或规划步骤真正需要的紧凑视图，只读不写。
  output-language: zh-CN
  execution-mode: shared-contract
  phase: shared
  critical-path: false
  learner-facing: false
  state-write-mode: none
  parallel-safe: true
  latency-class: interactive
  provider: 
  ownership: shared
---

# 学习档案读取

## 角色

`learning_profile` 是系统唯一的学习者真相源。任何 agent 都可以读它，**没有任何 agent 可以写它**：
写入只经由 `state/profile_writer.py`，且必须引用 `learning_evidence` 行。这个 skill 描述"怎么读"。

## 读什么

一行档案 = 一个用户 × 一个知识点。字段分两层：

| 层 | 字段 | 用途 |
| --- | --- | --- |
| 用户列 | `knowledge_point` `mastery` `learning_state` `progress` `my_questions` `recent_performance` `last_studied_at` `review_due_at` `next_step` | 可以直接展示给学习者 |
| 系统列 | `confidence` `evidence_count` `misconceptions` `prerequisites` `difficulty` `review_priority` `stability` `source_agent` `revision` `override_flag` | 供规划与排序使用，不直接展示 |

## 投影规则

1. **只取当前目标涉及的知识点，外加它们的 `prerequisites` 一层**。整表投影会把无关知识点
   带进模型上下文，既贵又会稀释注意力。
2. **`mastery` 必须和 `confidence`、`evidence_count` 一起读**。`mastery=0.8` 而
   `evidence_count=1` 不是"掌握了"，是"只看过一次"。把它当作已掌握是最常见的误判。
3. **`override_flag=true` 的行，`mastery` / `learning_state` / `progress` / `difficulty` /
   `next_step` 是学习者自己写的**。可以引用，不要在推理里把它当作系统观测。
4. **`review_due_at` 过期不等于"忘了"**，只等于"该验证了"。结论要靠新证据，不靠时间。
5. `misconceptions` 非空时，优先针对误区讲解，而不是重复原讲解。

## 输出形状

投影结果建议压成下面这种最小结构再进模型：

```json
{
  "target": {"id": "tcp-congestion", "mastery": 0.32, "state": "emerging",
             "evidence_count": 3, "confidence": 0.6, "misconceptions": ["把拥塞窗口当成接收窗口"]},
  "prerequisites": [{"id": "sliding-window", "mastery": 0.21, "state": "unknown", "evidence_count": 0}],
  "due_for_review": [{"id": "three-way-handshake", "review_priority": 0.81}]
}
```

## 反模式

- 把整张档案表塞进 prompt。
- 只读 `mastery`，忽略 `confidence` 和 `evidence_count`。
- 读完之后直接改档案（任何形式的写入都会被 `tests/test_profile_write_guard.py` 拦下）。
- 用自然语言把档案转述给下一个 agent；下一个 agent 自己读表。
