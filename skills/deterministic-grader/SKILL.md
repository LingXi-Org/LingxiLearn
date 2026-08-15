---
name: deterministic-grader
description: >-
  Grade a learner attempt with the course pack's deterministic graders and emit the resulting
  evidence. Use whenever an attempt can be judged by rule; a model opinion is not a grade.
license: MIT
metadata:
  author: LingXi-Org
  version: 1.0.0
  display-name: 确定性判分
  display-description: 用课程包的确定性判分器判分并产出证据，能按规则判的就不要交给模型。
  output-language: zh-CN
  output-contract: grading-result.v1
  execution-mode: deterministic-evaluation
  phase: assess
  critical-path: true
  learner-facing: false
  state-write-mode: none
  parallel-safe: false
  latency-class: interactive
  capabilities: assess.grade
  status-line: 正在核对你的作答…
  provider: deterministic_grader
  ownership: dedicated
---

# 确定性判分

## 角色

掌握度是系统对学习者的正式判断，它必须建立在可复现的判分上。模型可以解释判分结果，
**不能代替判分**。宿主的 `kernel/graders.py` 是权威实现，这里描述它的使用契约。

## 判分器类型

| grader | 适用 | 判定 |
| --- | --- | --- |
| `exact` | 单选、精确值 | 归一化后完全相等 |
| `numeric` | 数值题 | 落在 `tolerance` 内 |
| `set` | 多选 | 集合相等，可配 `partial_credit` |
| `keywords` | 简答 | 命中必需关键词集合的比例 |
| `tool` | 需要工具核查的题 | 与工具输出比对 |

## 规则

1. **先判分，再解释**。顺序反过来会让解释影响分数。
2. **分数是观测值**。判分器给 0.4 就产出 0.4 的证据，不要因为「他思路对」改成 0.7；
   思路对属于另一条 `error_pattern` 证据。
3. **误区标签取自课程包的 `misconception` 分类**，不要每次新造措辞——
   `learning_profile.misconceptions` 按标签聚合，措辞漂移会让同一个误区看起来像五个。
4. **答不出也是证据**：产出 `no_answer`，`score=0.0`，不要跳过。跳过会让
   `evidence_count` 停滞，掌握度估计永远处于「不可信」。
5. **提示层级必须随分数一起产出**。H3 提示下答对的信息量远低于 H0，
   掌握度按 `kernel/mastery.py::hint_discount` 打折。
6. 判分器不可用或题目没有判分规则 → 走 `graceful-degradation`：保留作答证据，
   标 `needs_recheck`，**不要猜分数**。

## 输出契约 `grading-result.v1`

```json
{
  "per_item": [
    {"item_id": "q3", "knowledge_point": "tcp-congestion", "score": 0.0,
     "correct": false, "hint_level": 2,
     "misconceptions": ["把拥塞窗口当成接收窗口"],
     "detail": "答案写成 rwnd 决定发送速率"}
  ],
  "overall": 0.33,
  "needs_recheck": [],
  "evidence": [{"signal": "incorrect", "knowledge_point": "tcp-congestion",
                "score": 0.0, "hint_level": 2}]
}
```

## 反模式

- 让模型「综合评估」一道有明确答案的题。
- 把部分分给成「鼓励分」。
- 判分结果不产出证据，只写进回复文本——那样档案永远不动。
