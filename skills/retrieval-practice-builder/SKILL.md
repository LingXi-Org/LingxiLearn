---
name: retrieval-practice-builder
description: >-
  Build and prefetch one evidence-grounded retrieval, transfer, boundary-case, or misconception-
  discriminator task from taught content and learner evidence. Use after a concept checkpoint or
  while the learner is answering another task; discard the cache when the topic or evidence changes.
  Do not use it as a blocking tutor or as a replacement for deterministic grading.
license: MIT
metadata:
  author: LingXi-Org
  version: 1.0.0
  display-name: 检索练习构建器
  display-description: 预取基于学习证据的检索、迁移、边界和误区辨析任务。
  output-language: zh-CN
  output-contract: retrieval-practice-builder-result.v1
  execution-mode: non-blocking-structured-generation
  phase: assess
  critical-path: false
  learner-facing: artifact
  state-write-mode: none
  parallel-safe: true
  latency-class: background
  eval-suite: retrieval-practice-builder-v1
---

# Retrieval Practice Builder

## Role

Generate a small cache of candidate tasks and select one next task for later use. This Skill is a
prefetch sidecar, not a learner-facing chat writer, assessor, grader, or tutor. `adaptive-pedagogy`
decides whether the selected artifact is still appropriate when the learner's next event arrives.
The host may discard the cache without penalty.

Read `references/retrieval-practice-builder-task.schema.json` and
`references/retrieval-practice-builder-result.schema.json`. Read
`references/design-rules.md` for target types and candidate quality, then apply
`references/quality-gate.md`.

## Runtime contract

Run from taught content and structured learner evidence. Prefer running while the learner is working
on the current task so the next task is ready before it is needed. Never block the current response,
wait for learner-state persistence, or call another Skill. Set `prefetch.blocking=false` and include a
discard condition for topic or evidence changes.

The primary output is a cache envelope with a learner-safe `public_task` and a separate internal
`grading_key`. The public task may later be rendered by the host, but this Skill does not send it to
the learner or add a second conversational response.

## Candidate workflow

1. Treat the supplied taught content, objective, learner evidence, and evidence references as the
   evidence boundary. Do not browse or add external facts.
2. Select a target type from `retrieval`, `near_transfer`, `far_transfer`, `boundary_case`, and
   `misconception_discriminator`. Choose the smallest target that can change the next support action.
3. Generate up to three genuinely different candidates. Each candidate must be answerable from the
   evidence boundary, independently solvable, and tied to at least one evidence reference.
4. Validate answerability, one-main-judgment focus, misconception coverage, difficulty, and public /
   internal separation. Reject candidates that depend on an unshown figure, hidden page state, or
   cold knowledge.
5. Select one candidate only when its task is better supported than the alternatives. If evidence is
   too thin, return `status=insufficient_evidence`, no public task, and a Chinese warning.

## Difficulty and independence

Difficulty comes from reasoning distance, not obscure wording. A retrieval item asks for the taught
relation; near transfer changes the surface context; far transfer changes the application; a boundary
case probes the limit of a rule; a misconception discriminator separates two plausible rules.

Do not count an assisted answer as independent evidence. If `verification_debt` is present, prefer a
short independent retrieval or near-transfer task and keep the answer in `grading_key` only.

## Result requirements

Return `retrieval-practice-builder-result.v1` with candidates, selection, `public_task`, `grading_key`,
validation details, evidence references, and a non-blocking prefetch envelope. Every learner-visible
prompt, option, label, and warning must be Simplified Chinese. Never put `answer`, `explanation`,
`rubric`, `keywords`, or internal assumptions inside `public_task`.

Validate with:

```text
python scripts/retrieval_contract.py validate-task <task.json>
python scripts/retrieval_contract.py validate-pair <task.json> <result.json>
```

