---
name: tool-investigator
description: >-
  Run the course pack's registered deterministic tools over real artifacts and turn the output
  into citable evidence. Use when a claim can be checked instead of asserted.
license: MIT
metadata:
  author: LingXi-Org
  version: 1.0.0
  display-name: 工具核查
  display-description: 对真实材料运行课程包注册的确定性工具，把输出变成可引用的证据。
  output-language: zh-CN
  output-contract: investigation-result.v1
  execution-mode: deterministic-evaluation
  phase: investigate
  critical-path: false
  learner-facing: false
  state-write-mode: none
  parallel-safe: true
  latency-class: interactive
  capabilities: tool.investigate
  status-line: 正在核查相关资料…
  provider: pack_investigate
  ownership: dedicated
---

# 工具核查

## 角色

「能算的不要猜」。课程包声明能力名，`tools/registry.py` 解析成真实 Python。
这个 skill 负责挑对工具、传对参数、把输出变成带 id 的证据。

## 规则

1. **工具按能力名解析**，不要在教学逻辑里直接 import 领域模块。
   新增学科 = 注册新命名空间，不是改这一步。
2. **工具失败是教学素材，不是 500**。`ToolResult.ok=False` 时把失败原因作为
   `error_pattern` 证据保留，并把失败情况告诉学习者。
3. **每个工具输出都进证据账本并拿到 id**。后续任何教学论断引用这个 id；
   引用不存在的 id 是硬错误（`kernel/evidence.py::verify_citations` 会抓）。
4. **不要把原始输出整包塞给模型**。抓包字节、完整表格、数据库原始记录先摘要，
   再进教学上下文。
5. 工具输出与学习者的答案冲突时，**以工具为准**，并把冲突本身记成误区证据。

## 输出契约 `investigation-result.v1`

```json
{
  "calls": [
    {"tool": "net.ipv4.lpm", "args": {"prefixes": ["10.0.0.0/8"], "address": "10.1.2.3"},
     "ok": true, "duration_ms": 3,
     "evidence_id": "ev_9f2c", "summary": "最长前缀匹配命中 10.0.0.0/8"}
  ],
  "failed": [],
  "warnings": []
}
```

## 反模式

- 让模型「心算」一个有工具能算的结果。
- 工具报错就让整个任务失败。
- 论断引用一个没有产出过的 evidence id。
