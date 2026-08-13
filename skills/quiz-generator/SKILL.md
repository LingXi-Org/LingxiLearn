---
name: quiz-generator
description: >-
  Generate a compact, evidence-grounded formative quiz from taught lesson content to assess understanding and reveal misconceptions.
license: MIT
metadata:
  author: LingXi-Org
  version: 1.1.0
  display-name: 知识点测评生成
  display-description: 基于已讲授的课程内容生成紧凑、可判分且能识别理解误区的形成性测评。
  output-language: zh-CN
  output-contract: quiz-generation-result.v1
  execution-mode: synchronous-structured-generation
  phase: assess
  critical-path: false
  learner-facing: artifact
  state-write-mode: none
  parallel-safe: true
  latency-class: background
  eval-suite: quiz-generator-v1
---

# Quiz Builder

## 目标

把已经讲授的知识点转化为一组短小、有诊断价值的形成性测评。它负责一次性的小型测评集；
下一回合的单个检索/迁移任务由 `retrieval-practice-builder` 负责。默认把本 Skill 作为可预取、可丢弃
的评测 artifact，不阻塞 `adaptive-pedagogy` 的即时回答，也不承担 assessor 或 learner-facing
辅导职责。测评不是第二篇讲义，也不是题库堆砌；它要帮助学习者暴露理解断点，帮助教师知道
下一步该补哪里。

默认一次生成 3–4 道题：先检查核心概念，再辨析一个有依据的误区，然后视材料质量加入应用、
预测、解释或迁移题。材料只支持一个可靠问题时，生成更少的题；不要为了凑齐题型而编造难题。

## 输入与输出

读取 `references/quiz-generation-input.schema.json`。输入应包含知识点意图和已讲授的交互课件；
课程引入可以是单文件 HTML、最小 JSON envelope，或缺省。把上游材料视为证据边界，不修改它，
也不要默认联网补课。

返回 `quiz-generation-result.v1`。题干、选项、说明、关键词和假设都使用简体中文；协议字段、
题目 ID 和枚举值保持技术形式。完整结果供内部判分使用；公开给学习者前，使用
`scripts/quiz_contract.py sanitize` 删除 `answer`、`explanation`、`keywords` 和 `assumptions`。

## 设计原则

- 测理解，不测未讲授的冷知识；每个正确答案都必须能在输入材料中找到依据。
- 一题只做一个主要判断。题干自包含，不依赖“上一页”“第 3 张幻灯片”或隐藏图形。
- 干扰项来自真实近错：反转因果、混淆邻近概念、漏掉必要条件、越过适用边界或把局部规律过度泛化。
- 单选题应有且只有一个可辩护答案；多选题只有在确实存在多个正确条件时使用。
- 选项保持相近的语法、长度和具体程度，打散正确选项位置，不用“以上都对/以上都不对”。
- 简答题通常要求 1–4 句，用概念与关系评分，不依赖逐字复述。
- 难度来自推理距离，不来自晦涩措辞或额外知识。材料不足时宁可少出一道题。
- 不把课程引入中的历史日期、人物轶事或装饰性事实自动变成考点，除非课件真正讲授并要求掌握。

## 工作流程

1. 校验输入版本，读取意图、课程引入和课件；提取中心概念、机制、定义、对比、例题、边界
   条件与明确学习目标。
2. 建立私有证据图：`概念 → 已讲授的事实/关系/例子/误区`。任何无法落到证据图的内容不出题。
3. 选择最少但信息量足够的题目。优先顺序通常是核心辨识 → 误区辨析 → 应用/预测 → 解释/迁移，
   但可以根据材料自由删减或调整。
4. 为每道题写答案、解释、评分信息和关键词；`total_points` 必须等于所有题目分值之和。
5. 按 `references/quality-gate.md` 做一次重写式审查，而不是只做形式检查。
6. 用 `scripts/quiz_contract.py validate-result` 校验，程序化调用时只返回 JSON，不包 Markdown 代码围栏。
7. 需要在当前回合展示时，先使用公开快照；不要把内部答案、解析或关键词交给 learner-facing writer。

## 证据不足与冲突

不要用外部搜索修补上游材料的空白。若材料稀疏，生成更少、更安全的问题，并在内部
`assumptions` 中记录限制；如果一个选择题无法构造唯一可信答案，改成有评分标准的简答题，
或直接省略。材料互相冲突时保留不确定性，不把猜测写成答案。

## 公开快照

内部结果和学习者看到的题目必须分离。公开快照只保留可渲染内容：题目 ID、题型、题干、选项和
分值。不得泄露答案、解析、关键词、假设或任何能反推出正确选项的内部信息。
