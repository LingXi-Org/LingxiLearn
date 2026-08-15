---
name: learning-report
description: >-
  Write the end-of-goal report from the profile diff and the evidence ledger. Use when a goal is
  satisfied; every claim must cite evidence that exists.
license: MIT
metadata:
  author: LingXi-Org
  version: 1.0.0
  display-name: 学习报告
  display-description: 在目标达成时基于档案前后差异和证据账本写报告，每条论断都必须引用真实存在的证据。
  output-language: zh-CN
  output-contract: learning-report.v1
  execution-mode: synchronous-structured-generation
  phase: report
  critical-path: false
  learner-facing: true
  state-write-mode: none
  parallel-safe: true
  latency-class: background
  capabilities: meta.report
  status-line: 正在整理学习报告…
  provider: pack_report
  ownership: dedicated
---

# 学习报告

## 角色

报告不是总结聊天记录，是把**档案的前后差异**讲清楚：学了什么、证据是什么、还差什么。

## 素材

- `decision_trace` 里每一步的 `profile_before` / `profile_after`
- `learning_evidence` 中本次目标涉及的证据行
- 目标栈里该目标的 `expected_outcome`

## 规则

1. **每条论断引用 evidence id**。「你已经掌握了拥塞控制」必须挂上具体作答；
   引用不存在的 id 是硬错误。
2. **报告掌握度变化，不报告努力程度**。「你很认真」不是学习结果。
3. **明确写出还没验证的部分**。`evidence_count < 2` 的点写成「尚未充分验证」，
   不要写成「已掌握」。
4. **误区要写清是消解了还是仍在**。消解需要有新的、相反方向的证据支撑。
5. **给出下一步**，且下一步要落到 `learning_profile.next_step` 那种可点击形状，
   不要写成「继续加油」。
6. 中文，简短。三段以内：学到了什么 / 证据 / 下一步。

## 输出契约 `learning-report.v1`

```json
{
  "goal_id": "goal_7a1c",
  "summary": "面向学习者的中文小结",
  "mastery_changes": [
    {"knowledge_point_id": "tcp-congestion", "before": 0.32, "after": 0.61,
     "evidence_ids": ["ev_a1b2", "ev_c3d4"]}
  ],
  "resolved_misconceptions": ["把拥塞窗口当成接收窗口"],
  "open_misconceptions": [],
  "unverified": ["fast-retransmit"],
  "next_step": {"capability": "assess.generate", "knowledge_point_id": "fast-retransmit",
                "label": "测一测快速重传", "rationale": "只讲过一次，还没有作答证据"}
}
```

## 反模式

- 复述对话过程。
- 把「看完了课件」当成掌握证据。
- 结尾写一句「继续保持」就算下一步。
