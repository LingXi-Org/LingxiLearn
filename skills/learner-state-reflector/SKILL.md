---
name: learner-state-reflector
description: >-
  Compress recent learning events into cautious, traceable learner-state update proposals without interrupting instruction.
license: MIT
compatibility: LingxiGraph Agent Skills runtime
metadata:
  author: LingXi-Org
  version: 1.0.0
  display-name: 学习状态反思
  display-description: 将近期学习事件整理为谨慎、可追溯的学习状态更新建议，不打断教学流程。
  output-language: zh-CN
  output-contract: learner-state-reflector-result.v1
  execution-mode: non-blocking-background
  blocking: "false"
---

# State Observer

## Role

Run after or alongside the already-rendered student-facing response. Remove memory and evidence
compression work from the learner's critical path. Never make this skill a dependency that
`adaptive-pedagogy` must await.

## Output language

Write all prose, learner-model claims, labels, and suggestions in Simplified Chinese. Preserve
protocol keys, evidence IDs, concept paths, file names, URLs, and schema tokens in their original
form. Return `learner-state-reflector-result.v1`.

## Hard rules

1. Never produce a required student reply or a student-facing tutoring message.
2. Preserve raw evidence IDs so every proposal is traceable.
3. Prefer categorical evidence states over false precision.
4. Never infer intelligence, motivation, disability, personality, mental health, or learning style.
5. Store confidence only when the learner explicitly supplied it or the UI captured it.
6. Treat an open learner-model card as optional UI; never interrupt the lesson for agreement.

## Inputs

Read `references/learner-state-reflector-task.schema.json`. Process independent answers, answers
after hints, local hint levels, support choices, visual predictions or observations, teach-back
explanations, learner-model challenges, and direct explanations shown.

## Evidence compression

For each concept, record only supported states:

- `not_observed`
- `emerging`
- `demonstrated`
- `misconception_evidence`
- `needs_recheck`

Keep whether evidence was independent or assisted, its recency, repeated patterns, and evidence
IDs. Never convert one correct answer into permanent mastery.

## Verification debt and prefetch

Propose a `verification_debt` item when a strong hint or complete solution was shown without later
independent evidence. Propose discharging it after an independent retrieval or transfer task
succeeds. Suggest the next natural checkpoint; do not schedule an immediate question.

Optional prefetch suggestions may include a likely next concept, a visual brief, or one branch note.
They are caches only, and `adaptive-pedagogy` must check them against the next learner message.

## Optional learner-model card

When useful, return a non-blocking card with Chinese claims and the actions `我不同意` and
`让我证明`. Do not require the learner to accept it.

## Required result

Return `evidence_summary`, `state_update_proposals`, and `verification_debt_proposals`, plus
optional `learner_model_card` or `prefetch_suggestions`. Every prose value must be Chinese. Do
not return a tutoring message, a diagnosis, or a mandatory learner action.
