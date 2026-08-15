---
name: graceful-degradation
description: >-
  Keep the runtime loop moving when a model, tool, or artifact step fails. Use on any failure
  path; a failed step must degrade to a usable result, never stall the loop.
license: MIT
metadata:
  author: LingXi-Org
  version: 1.0.0
  display-name: 降级回退
  status-line: 正在保留已完成的内容…
  display-description: 在模型、工具或产物步骤失败时让运行时循环继续，失败必须降级成可用结果而不是卡住。
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

# 降级回退

## 角色

自主循环最危险的失败不是出错，是**停住**。学习者对着一个不动的界面，比拿到一个稍差的结果糟糕得多。
每条失败路径都必须有下一步。

## 降级阶梯

按顺序尝试，能停在哪一级就停在哪一级：

1. **重试一次**——仅限幂等步骤（读档案、解析、校验）。非幂等步骤（生成产物、写证据）不重试。
2. **确定性回退**——不用模型也能产出的结果：
   - 排序失败 → 直接取候选集打分最高的那个（argmax），不问模型。
   - 讲解生成失败 → 用课程包的提示阶梯 `hint_ladder` 里当前层级那一条。
   - 产物生成失败 → 用宿主预置的 fallback 页面。
   - 判分失败 → 保留作答证据，标 `needs_recheck`，不猜分数。
3. **缩小范围**——把一个大任务换成它的最小可交付部分（整套课件 → 一页引入）。
4. **交还给学习者**——`awaits_user=true`，说明发生了什么和可选项。
5. **标记 FAILED**——只有前四级都不可行时。必须带一句学习者能看懂的中文原因。

## 必须遵守

- **降级要留痕**：每次降级产出一条 `error_pattern` 证据和一条 decision trace，
  否则评测会把降级结果当成正常结果统计。
- **不要伪装成功**：降级结果要在响应里标明是回退版本。
- **不要吞掉预算**：降级不重置 `max_steps` / `max_replans`，否则失败会变成无限循环。
- **不可逆操作永不自动降级重试**：写图谱、建日程、启用 forged skill 失败就停下来问。

## 反模式

- `except Exception: pass`，然后循环继续转但状态没变。
- 用模型去处理"模型不可用"。
- 降级之后不告诉学习者，让他以为拿到的是完整结果。
