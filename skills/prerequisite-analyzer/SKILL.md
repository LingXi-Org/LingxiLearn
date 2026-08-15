---
name: prerequisite-analyzer
description: >-
  Determine what a target knowledge point rests on and which of those prerequisites the learner
  has not met yet. Use before teaching anything non-trivial; the result decides whether the
  runtime teaches the request or the thing under it.
license: MIT
metadata:
  author: LingXi-Org
  version: 1.0.0
  display-name: 前置依赖分析
  display-description: 判断目标知识点依赖什么、学习者还差哪一层，决定先讲请求本身还是先补下面那一层。
  output-language: zh-CN
  output-contract: prerequisite-analysis-result.v1
  execution-mode: synchronous-structured-generation
  phase: learner-model
  critical-path: false
  learner-facing: false
  state-write-mode: none
  parallel-safe: true
  latency-class: interactive
  capabilities: graph.prerequisite
  status-line: 正在分析前置知识…
  provider: prerequisite_analyzer
  ownership: dedicated
---

# 前置依赖分析

## 角色

「先补前置知识」是运行时唯一被允许违背用户字面要求的教学动作。这个判断必须有依据，
所以这一步要产出**具体的、可核查的依赖结论**，而不是「基础不牢」。

## 输入

- 目标知识点 id 与标签
- 该点及候选前置点的 `learning_profile` 行（含 `mastery`、`evidence_count`、`misconceptions`）
- 可用的课程知识图谱片段（若存在）

## 判定规则

1. **只列真正的推导依赖**。「学 TCP 之前最好懂点网络」不是依赖；「推导 cwnd 变化要用到发送窗口
   的边界」是依赖。一个前置点必须能指出它在目标推导里被用在哪一步。
2. **深度最多两层**。再往下就不是教学决策而是课程重排。
3. **前置是否满足看证据，不看时间**：`mastery >= 0.6` 且 `evidence_count >= 2` 才算满足；
   `evidence_count < 2` 时无论 `mastery` 多高都标 `unverified`，而不是 `met`。
4. **误区优先于薄弱**：前置点带未消解 `misconceptions` 时，即使 `mastery` 达标也标 `blocked`。
5. 找不到可靠依赖就返回空列表并说明，不要编一条出来凑数。

## 输出契约 `prerequisite-analysis-result.v1`

```json
{
  "target": "tcp-congestion",
  "prerequisites": [
    {"id": "sliding-window", "label": "滑动窗口", "status": "blocked",
     "used_for": "推导 cwnd 与 rwnd 的取小关系",
     "mastery": 0.21, "evidence_count": 3,
     "evidence_ids": ["ev_a1b2", "ev_c3d4"]}
  ],
  "verdict": "teach_prerequisite_first",
  "blocking_prerequisite": "sliding-window",
  "rationale": "拥塞窗口的每一步推导都要用到发送窗口边界，而该点 3 次作答只对 1 次。",
  "warnings": []
}
```

`status` 只能是 `met` / `unverified` / `blocked`。
`verdict` 只能是 `teach_target` / `teach_prerequisite_first` / `verify_prerequisite_first`。

## 反模式

- 把课程目录顺序当成依赖关系。
- 列出五六个前置点——那是大纲，不是决策。
- 以「没有数据」为由判定前置未满足；没有数据应当先测（`verify_prerequisite_first`）。
