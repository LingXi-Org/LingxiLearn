---
name: artifact-validator
description: >-
  Validate a generated artifact against its delivery contract before it reaches the learner. Use
  after any artifact-generating step; a model receipt claiming success is not validation.
license: MIT
metadata:
  author: LingXi-Org
  version: 1.0.0
  display-name: 产物校验
  status-line: 正在校验产物完整性…
  display-description: 在产物交付给学习者之前按交付契约校验，模型自称成功不算校验。
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

# 产物校验

## 角色

生成 agent 会在写完文件之前、之后、甚至没写文件的情况下都返回"成功"。**回执不是校验**。
宿主在发布任何学习者可见产物之前必须跑一次确定性校验。

## 各产物的校验点

### `lesson-intro.html`
- 单文件、零外部请求、UTF-8、`lang="zh-CN"`。
- 存在 `<title>`、`<main>`、至少一个 `<figure>` 或 `<svg>`。
- 明暗两套配色都定义了（`prefers-color-scheme` 或等价 token）。
- 校验失败时回退到宿主预置的 fallback 页面，**不要交付坏页面**。

### `lecture-deck`
- `lecture.json` 必须是 v2：每个 anchor 有 `id`/`label`/`rect` 对象（不是数组）；
  每个 step 有 `advance`；overview 的 camera 只能是 `{"mode":"fit"}`。
- 每页 slide 根节点直接子块 ≤ 8（硬上限 10）。
- 每个 `<text>` 带 `class` 之一：`t`/`ts`/`th`/`tn`。
- `runtime/index.html` 由宿主预置，生成方不得覆盖。
- `dist/lecture.html` 由服务端 standalone build 产出。

### `visual-explainer.html`
- 单文件、离线、无外部请求；支持明暗与打印。
- 通过 palette 检查与静态检查。

### quiz 结果
- 符合 `quiz-generation-result.v1`；`total_points` 等于各题 `points` 之和。
- 答案、解析、keywords 属内部字段，**不得进入面向学习者的快照**。

## 失败处理顺序

1. 能修就地修（结构性小错，如 rect 写成数组）。
2. 修不了就回退到已知可用版本，并在 `warnings` 里写明中文原因。
3. 两者都不行才让这一步失败，并产出一条 `error_pattern` 证据。

## 反模式

- 相信模型的 `{"status":"ok"}`。
- 把校验失败的产物交付出去，只在日志里记一行 warning。
- 校验失败就整个任务失败——学习者会因此丢掉本来可用的材料。
