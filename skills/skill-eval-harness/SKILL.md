---
name: skill-eval-harness
description: >-
  Evaluate Lingxi teaching Skills and their run artifacts across component contracts, execution
  trajectories, pedagogical safety/quality, and learner outcomes. Use when a Skill is added or
  revised, when a regression suite must be run, or when raw task/result/trace/outcome JSON needs a
  deterministic report; do not use it in the learner's runtime path.
license: MIT
metadata:
  author: LingXi-Org
  version: 1.0.0
  display-name: 教学 Skill 评测
  display-description: 从组件契约、执行轨迹、教学质量和学习结果四层评测教学 Skill。
  output-language: zh-CN
  output-contract: skill-eval-report.v1
  execution-mode: development-deterministic-evaluation
  phase: development
  critical-path: false
  learner-facing: false
  state-write-mode: none
  parallel-safe: true
  latency-class: offline
  capabilities: meta.evaluate
  status-line: 正在检查技能表现…
  provider: skill_eval
  ownership: dedicated
  eval-suite: skill-eval-harness-v1
---

# Teaching Skill Evaluation

Use this development-time Skill to turn raw evaluation cases into a comparable, traceable report.
It evaluates an existing Skill's contract and observed artifacts; it does not generate teaching
responses, replace a deterministic grader, or write learner state.

## Evaluation workflow

1. Build a `skill-eval-run.v1` JSON file. Keep the learner task and raw output in each case; put
   expected answers, forbidden strings, thresholds, and rubric-only labels in `expectations`, not in
   the learner prompt.
2. Include an execution `trajectory` whenever latency, blocking, handoffs, repeated questions, or
   sidecar behavior matters. Include an `outcome` when an independent transfer or post-test is
   available. Missing layers are reported as `not_observed`, not silently treated as success.
3. Read `references/skill-eval-run.schema.json` and `references/rubric.md` for the case shape and
   layer rules. Use the smallest raw artifact that still preserves evidence IDs and timing.
4. Run the deterministic helper:

   ```text
   python scripts/evaluate.py validate-run <run.json>
   python scripts/evaluate.py evaluate <run.json> --output <report.json>
   python scripts/run_suite.py <repository-root> --output <suite-report.json>
   ```

   Individual reports follow `references/skill-eval-report.schema.json`; repository-wide suite
   reports follow `references/skill-eval-suite-report.schema.json`.

5. Review every failing finding and the observed coverage. Set `expectations.required_layers` for
   layers that a case must observe; a missing required layer fails the case. A Skill passes only when the component
   layer has no errors and every layer required by the case expectations passes. Do not hide missing
   learner outcomes behind a high component score.

## Four evaluation layers

- **component** — frontmatter, execution metadata, required output fields, known result contracts,
  and artifact shape.
- **trajectory** — one learner-facing writer, no accidental handoff loop, no repeated prompt without
  new evidence, sidecars not blocking the response, and latency/token/hop budgets.
- **pedagogy** — answer leakage, evidence grounding, hint/reveal limits, question-value discipline,
  and usable fallback for non-blocking visual work.
- **learner_outcome** — independent transfer, score change when a threshold is supplied, verification
  debt discharge, and evidence traceability.

Use `validator` values for the bundled contracts (`adaptive-pedagogy-result.v2`,
`learner-state-reflector-result.v1`, `quiz-generation-result.v1`,
`curriculum-graph-builder-result.v1`, `formative-assessor-result.v1`,
`retrieval-practice-builder-result.v1`, `lesson-intro-html.v1`, `html`) or provide
`required_output_keys` for another Skill. The harness performs deterministic checks only; judgments
such as whether a misconception interpretation is pedagogically sound still require human review or
a separately specified judge.

## Evaluation boundaries

- Keep expected answers outside learner-facing text and do not pass the intended fix to a forward
  test agent.
- Treat `learner-state-reflector`, visual generation, quiz generation, and remedial artifacts as
  sidecars unless the case explicitly tests their standalone artifact contract.
- Enforce `learner_facing_writer_count <= 1` for a learner turn.
- Report latency and token measurements supplied by the host; never invent measurements.
- Keep expected answers outside the learner-facing paths used by leakage checks. For retrieval tasks,
  inspect `public_task`, never the internal `grading_key`.
- For `lesson-intro-html.v1`, check the shared visual contract as well as basic HTML shape: tokenized
  palette, 680-wide SVG, figure caption, dark/print modes, no gradients/shadows, and restrained
  typography.
- Never mutate the tested Skill or learner data. Write only the requested report file.

## Result contract

Return `skill-eval-report.v1` JSON with per-case findings, four layer scores, observed coverage,
thresholds, and a concise overall status. Preserve case IDs, evidence IDs, and raw metric values so a
failing report can be traced back to the source artifact.

`run_suite.py` discovers checked-in `skills/*/assets/eval-run.json` files, evaluates each suite, and
returns `skill-eval-suite-report.v1`. It is intended for development and CI, never for student
runtime.
