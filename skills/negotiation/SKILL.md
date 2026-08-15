---
name: negotiation
description: >-
  Write the one-sentence negotiation a learner sees when the system intends to do something other
  than what they literally asked for. Use whenever the ranked plan deviates from the stated
  request; the system may deviate, but never silently.
license: MIT
metadata:
  author: LingXi-Org
  version: 1.0.0
  display-name: 教学协商
  display-description: 当系统打算偏离用户字面要求时，写出那一句协商话术。可以不照做，但不能不打招呼。
  output-language: zh-CN
  execution-mode: shared-contract
  phase: teach
  critical-path: true
  learner-facing: true
  state-write-mode: none
  parallel-safe: true
  latency-class: interactive
  capabilities: dialog.negotiate
  status-line: 正在和你协商下一步…
  provider: negotiator
  ownership: dedicated
---

# 教学协商

## 角色

系统被允许不按用户字面要求执行——例如用户要讲「TCP 拥塞控制」，但档案显示前置的
「滑动窗口」`mastery=0.21`，先补前置的学习收益更高。**允许偏离，但必须先协商一句再做。**
护栏会拒绝任何"偏离目标但没有协商话术"的计划。

## 一句协商包含什么

1. **承认原始请求**——让学习者知道没有被忽略。
2. **给出偏离的具体理由**——引用档案里的事实，不是"为了你好"。
3. **说明打算先做什么，要花多久**。
4. **留一个明确的拒绝出口**——学习者可以坚持原计划。

## 模板

> 你想学的是{原目标}。我看到{前置知识}你目前只做对过 {n} 次里的 {k} 次，
> 直接讲{原目标}大概率会卡在{具体卡点}。我建议先用 {时长} 把{前置知识}过一遍再回来——
> 你也可以让我直接讲{原目标}，我就按你说的来。

## 示例

> 你想学的是 TCP 拥塞控制。我看到「滑动窗口」你目前只做对过 3 次里的 1 次，
> 而拥塞窗口的推导要一直用到发送窗口的边界，直接讲大概率会卡在 cwnd 和 rwnd 的区别上。
> 我建议先用 8 分钟把滑动窗口过一遍再回来——你也可以让我直接讲拥塞控制，我就按你说的来。

## 规则

- **一句到两句，不要一段**。协商不是讲课。
- **引用具体数字**，"你基础不太好"不是理由，"3 次里对 1 次"是。
- **不要道歉式措辞**（"不好意思打断一下"）；这是教学判断，不是冒犯。
- **不要既协商又直接开始做**。协商的那一轮 `awaits_user=true`，等回复。
- 学习者坚持原计划时，照做，并把这次偏好记成 `self_report` 证据。

## 反模式

- 静默改计划（护栏会拒绝）。
- 用"根据我的分析"代替具体档案事实。
- 把协商写成选择题清单，让学习者做规划工作。
