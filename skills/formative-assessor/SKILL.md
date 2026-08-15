---
name: formative-assessor
description: >-
  Convert deterministic grader, rubric, tool, and explicit learner signals into a structured
  formative-assessment interpretation for adaptive teaching. Use after a learner attempt when the
  host needs evidence state, error pattern, verification status, or a policy signal; do not use it
  to guess learner psychology or write a student-facing response.
license: MIT
metadata:
  author: LingXi-Org
  version: 1.0.0
  display-name: 形成性评估解释器
  display-description: 将确定性判分证据转为可追溯的学习证据状态和教学策略信号。
  output-language: zh-CN
  output-contract: formative-assessor-result.v1
  execution-mode: synchronous-structured-generation
  phase: assess
  critical-path: true
  learner-facing: false
  state-write-mode: none
  parallel-safe: false
  latency-class: interactive
  capabilities: assess.interpret
  status-line: 正在分析你的作答证据…
  provider: formative_assessor
  ownership: dedicated
  eval-suite: formative-assessor-v1
---

# Formative Assessor

## Role

Interpret supplied deterministic evidence; do not re-grade the learner and do not produce a tutoring
message. A Supervisor may call this Skill as a bounded manager-as-tools capability after a judge or
trusted tool has returned evidence. The result informs `adaptive-pedagogy`, which remains the only
learner-facing writer.

Use `references/formative-assessor-task.schema.json` and
`references/formative-assessor-result.schema.json` for the exact contract. Use
`references/evidence-policy.md` for the evidence-to-policy mapping and
`references/quality-gate.md` before returning.

## Evidence boundary

Treat `grader_evidence`, explicit learner confidence, hint history, tool observations, and
`evidence_refs` as the complete evidence boundary. Never browse, invent an error pattern, or infer
intelligence, motivation, personality, disability, mental health, or learning style. Confidence is
valid only when the learner supplied it or the host captured it in a UI event; never infer confidence
from wording or tone.

If correctness is ambiguous, ungraded, or contradicted by the supplied records, set
`next_probe_needed=true` and explain the missing evidence. Do not resolve ambiguity by guessing.

## Interpretation workflow

1. Check the task version, concept, deterministic correctness, independence, assistance history,
   explicit confidence, error pattern, and evidence IDs.
2. Assign one evidence state. Treat `demonstrated` as evidence for this event, not permanent mastery.
3. Preserve the supplied error pattern; only name a pattern when the grader or rubric supports it.
4. Choose exactly one `recommended_policy_signal` that `adaptive-pedagogy` understands. The signal
   is a policy input, not a learner-facing explanation.
5. Set `next_probe_needed` only when another independent observation can change the next support
   action. Add `probe_reason` whenever it is true.
6. Return structured Chinese prose and raw `evidence_refs`; never include `student_response`,
   `tutoring_message`, `question_to_learner`, or a mandatory learner action.

## Routing defaults

- Independent correct evidence: `demonstrated` → `advance` or a natural `transfer_check`.
- Assisted correct evidence: `emerging` or `needs_recheck` → `transfer_check` when independence is
  still unverified.
- Incorrect answer with a stable, rubric-supported rule and explicit high confidence:
  `misconception_evidence` → `conceptual_conflict`.
- Incorrect answer with low/unknown confidence and no stable rule: `needs_recheck` → `minimal_cue` or
  `progressive_hint`.
- Partial evidence: `emerging` → `minimal_cue`, `targeted_explanation`, or `transfer_check`.
- Ambiguous or ungraded evidence: `needs_recheck`, `next_probe_needed=true` → `retrieve_or_predict`.

## Runtime boundary

This Skill is conditionally blocking only when the host cannot safely interpret the evidence itself.
On a clear deterministic result, skip it. When called, return once and pass the structured result to
`adaptive-pedagogy`; never hand off to another assessor or tutor and never await learner-state,
visual, quiz, or graph sidecars.

## Validation

Use the bundled helper for deterministic checks:

```text
python scripts/assessor_contract.py validate-task <task.json>
python scripts/assessor_contract.py validate-pair <task.json> <result.json>
```

