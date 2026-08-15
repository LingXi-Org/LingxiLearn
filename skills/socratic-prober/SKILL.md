---
name: socratic-prober
description: >-
  在掌握度不确定或存在误区时向学习者确认理解。
metadata:
  version: 1.0.0
  display-name: 苏格拉底追问
  display-description: 通过一个短问题确认学习者的理解。
  phase: teaching
  capabilities: dialog.probe
  provider: probe_user
  parallel-safe: false
  critical-path: true
  blocking: true
  latency-class: interactive
  status-line: 正在确认你的理解…
  ownership: dedicated
---

# 苏格拉底追问

一次只问一个能区分理解程度的问题，不直接泄露答案。
