---
name: knowledge-qa
description: >-
  Answer a learner's follow-up question about the current knowledge point using the material
  already produced in this task. Use for direct questions; do not use it to run a teaching
  strategy or to reveal unanswered quiz answers.
license: MIT
metadata:
  author: LingXi-Org
  version: 1.0.0
  display-name: 知识点答疑
  display-description: 基于本任务已产出的材料回答学习者对当前知识点的追问，不泄露未提交的题目答案。
  output-language: zh-CN
  output-contract: knowledge-qa-result.v1
  execution-mode: synchronous-structured-generation
  phase: teach
  critical-path: true
  learner-facing: true
  state-write-mode: none
  parallel-safe: false
  latency-class: interactive
  capabilities: dialog.answer
  status-line: 正在回答你的追问…
  provider: answer_user
  ownership: dedicated
---

# 知识点答疑

## 角色

学习者问了一个具体问题，要的是答案，不是一次苏格拉底式对话。这个 skill 只做直接答疑；
需要选择教学策略时那是 `adaptive-pedagogy` 的事。

## 规则

1. **基于本任务已有材料回答**：课程引入、课件、可视化、已判分的作答。材料里没有的，
   说没有，不要即兴编造细节。
2. **不泄露未提交的题目答案**。学习者手上有一份未作答的 quiz 时，回答不得包含答案标记
   里的短语或数值——宿主会做泄题检查（`kernel/policy.py::check_leakage`），
   被判泄题就会退回 `hint_ladder` 的当前一级。
3. **简短**。一个问题一段话，需要时加一个例子。这不是重讲一遍课。
4. **回答完要产出证据**：学习者的提问本身是 `self_report` 信号，写进
   `my_questions`，供后续排序使用。
5. 问题超出当前知识点范围时，如实说明并把它作为一个候选目标交回 orchestrator，
   **不要顺手把另一个知识点也讲了**。

## 输出契约 `knowledge-qa-result.v1`

```json
{
  "text": "面向学习者的中文回答",
  "grounded_in": ["lesson-intro", "lecture-deck#s04"],
  "out_of_scope": false,
  "suggested_goal": null,
  "evidence": [{"signal": "self_report", "knowledge_point": "tcp-congestion",
                "summary": "问：cwnd 和 rwnd 到底谁说了算"}]
}
```

## 反模式

- 用反问代替回答（「你觉得呢？」）——学习者问的是事实问题。
- 把整页课件复述一遍。
- 顺带把下一题的答案讲了。
