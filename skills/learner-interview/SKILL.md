---
name: learner-interview
description: >-
  用少量问题了解学习者对目标知识点的起点，并产出结构化自我报告证据。
metadata:
  version: 1.0.0
  display-name: 了解你的基础
  display-description: 用两三个短问题摸清学习起点。
  phase: teaching
  capabilities: dialog.interview
  provider: learner_interview
  learner-facing: true
  critical-path: true
  blocking: true
  latency-class: interactive
  parallel-safe: false
  ownership: dedicated
---

# 学习起点访谈

只问两三个短问题，围绕当前知识点确认学习者已经会什么、哪里不确定、希望达到什么程度。
返回结构化 `EvidenceRecord`，信号使用 `SELF_REPORT`；不要写成长篇散文，也不要泄露检测答案。
