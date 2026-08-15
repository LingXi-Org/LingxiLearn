---
name: evidence-emitter
description: >-
  Emit structured learning evidence instead of prose claims about a learner. Use whenever an agent
  observes something about how the learner is doing; this is the only channel through which an
  agent may influence the learning profile.
license: MIT
metadata:
  author: LingXi-Org
  version: 1.0.0
  display-name: 学习证据产出
  status-line: 正在整理学习证据…
  display-description: 把对学习者的观察产出为结构化证据，这是 agent 影响学习档案的唯一通道。
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

# 学习证据产出

## 角色

agent 不能写档案，只能产出证据。`state_updater` 是唯一的消费者，它把证据折叠进
`learning_profile`。所以"我觉得他掌握了"没有任何作用；**只有证据行会改变系统状态**。

## 证据信号

| signal | 含义 | 是否必须带 score |
| --- | --- | --- |
| `correct` | 作答正确 | 是 |
| `incorrect` | 作答错误 | 是 |
| `no_answer` | 答不出、跳过、放弃 | 是（通常 0.0） |
| `self_report` | 学习者自述（"这块我不懂"） | 否 |
| `dwell_time` | 在某材料上的停留时长 | 否 |
| `error_pattern` | 识别出的错误模式 | 否 |
| `artifact_viewed` | 打开/看完了某个产物 | 否 |
| `hint_used` | 使用了第 N 级提示 | 否 |

## 规则

1. **一条证据只说一个知识点**。"他 TCP 和 UDP 都不熟"要拆成两行。
2. **`score` 是观测值，不是评价**。判分器给 0.4 就写 0.4，不要"感觉他其实会，给 0.7"。
3. **`hint_level` 必须如实填**。掌握度按提示层级打折（H0 全额、H3 五折）；瞒报提示层级会
   直接制造虚高的掌握度。
4. **自述不是作答**。`self_report` 不带分数，它影响 `my_questions` 和复习优先级，不直接抬掌握度。
5. **误区要给稳定标签**，不要每次换一种说法；`misconceptions` 是按标签聚合的。
6. 证据只追加，不修改。写错了就再写一条更正的观测，不要试图改旧行。

## 最小示例

```json
{"knowledge_point": "tcp-congestion", "signal": "incorrect", "score": 0.0,
 "source_agent": "deterministic_grader", "hint_level": 2,
 "misconceptions": ["把拥塞窗口当成接收窗口"],
 "summary": "在 q3 把 cwnd 与 rwnd 混用"}
```

## 反模式

- 产出一段自然语言让下一个 agent 去解析。
- 一条证据同时覆盖多个知识点。
- 因为"想让学习者有成就感"而抬高 score。
