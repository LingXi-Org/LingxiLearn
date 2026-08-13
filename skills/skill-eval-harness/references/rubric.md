# 评测量规

## 目录

- [Case expectations](#case-expectations)
- [Trajectory events](#trajectory-events)
- [Layer gates](#layer-gates)
- [Report interpretation](#report-interpretation)

## Case expectations

Each case may include:

```json
{
  "validator": "adaptive-pedagogy-result.v2",
  "required_output_keys": ["decision.strategy"],
  "evidence_ids": ["ev-1"],
  "require_evidence": true,
  "forbidden_strings": ["答案是"],
  "answer_tokens": ["42"],
  "max_required_actions": 1,
  "max_blocking_hops": 1,
  "max_latency_ms": 3000,
  "max_tokens": 1600,
  "min_score_gain": 0.1,
  "verification_debt_should_discharge": false,
  "traceability_required": true
}
```

`answer_tokens` and `forbidden_strings` are evaluator-side checks. Do not put them into the learner
task sent to a model. Use `learner_facing_paths` to restrict leakage checks when an output contains
both an internal result and a public snapshot.

## Trajectory events

`trajectory.turns` is an ordered array. Useful fields are `event`, `writer`, `audience`,
`question_id`, `new_evidence`, `sidecar`, `blocking`, `blocked_response`, `latency_ms`,
`prompt_tokens`, and `completion_tokens`. The host may also provide top-level
`learner_facing_writer_count`, `blocking_hops`, `latency_ms`, `prompt_tokens`, and
`completion_tokens`.

Mark background jobs with `sidecar: true` or `role: "sidecar"`. A sidecar is a failure when it is
marked blocking or when `response_blocked_by_sidecar` is true. A repeated `question_id` is a failure
unless the later turn declares `new_evidence: true`.

## Layer gates

Component errors are hard failures. For the other layers, a case fails when an observed required
gate fails; a missing optional layer is `not_observed`. The harness does not infer an outcome from a
correct answer in the same assisted turn: outcome evidence must be marked independent by the host.

Recommended required gates for `adaptive-pedagogy` are:

1. component contract and metadata;
2. trajectory writer count, blocking hops, and response latency;
3. evidence grounding, question-value gate, hint limit, and visual fallback;
4. independent transfer or a clearly recorded `not_observed` outcome.

## Report interpretation

Scores are the fraction of observed checks that pass within each layer. `not_observed` checks do not
inflate the score. Read `coverage` beside `score`: a perfect component score with no outcome data is
not evidence that the teaching strategy improved learning. Preserve the raw report and compare the
same suite ID across revisions.
