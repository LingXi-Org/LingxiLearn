---
name: structured-output
description: >-
  Produce and repair strict JSON contract output from a model turn. Use whenever a step's result
  is consumed by code rather than read by a human.
license: MIT
metadata:
  author: LingXi-Org
  version: 1.0.0
  display-name: 结构化输出
  status-line: 正在整理结构化结果…
  display-description: 产出并修复严格 JSON 契约输出，用于结果由代码消费而非人阅读的步骤。
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

# 结构化输出

## 角色

运行时的每一步都由代码消费。散文没有消费者。这个 skill 规定契约输出怎么写、怎么修。

## 规则

1. **只输出 JSON 对象**，不要 Markdown 代码围栏之外的解释、不要思考过程、不要前后寒暄。
2. **契约字段齐全**：缺字段比多字段更危险，缺字段会让下游拿到 `None` 继续跑。
3. **不要把大产物塞进 JSON**。HTML/SVG/课件通过 artifact 工具写文件，JSON 里只放回执。
4. **枚举值用契约里的原文**，不要翻译、不要同义替换（`emerging` 不是 `正在形成`）。
5. **数字就是数字**，不要 `"0.8"`、不要 `"约 0.8"`。
6. 面向学习者的文案字段用简体中文；协议键、schema token、文件名、公式、代码、URL 保持原样。

## 修复阶梯

宿主解析失败时按顺序尝试，不要一次就让整步失败：

1. 抽取第一个完整 JSON 对象（容忍围栏和前后散文）。
2. 用契约默认值补齐缺失的可选字段。
3. 用一次带错误信息的重试让模型自修（只重试一次）。
4. 仍失败 → 走 `graceful-degradation`，用确定性回退结果继续循环。

## 反模式

- 返回 `{"result": "```json ... ```"}` 这样的嵌套字符串。
- 把答案、解析等内部字段混进公开快照。
- 用 `null` 表示"我不知道"却不带 `warnings` 说明。
