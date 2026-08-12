# Strategy kernel

These strategies execute **inside `adaptive-pedagogy`**. They are not separate SubAgents.

## `retrieve_or_predict`

Use when the lesson just ended and there is no usable learner evidence.

Design:
- one question only;
- prefer a generative prompt over recognition when feasible;
- choose a prompt whose possible answers separate meaningful learner models.

Example:
> 学习率如果非常大，你预测梯度下降轨迹会怎样？一句话说明原因。

Not:
> 你理解了吗？为什么？有多确定？举个例子。

## `minimal_cue`

Use for a likely slip, fragile retrieval, or low-confidence error.

Reveal:
- relevant condition, direction, or starting point;
- not the full reasoning chain.

Example:
> 先只比较两个数的十分位。

## `progressive_hint`

Use when the learner wants help but can still do useful work.

Generate 1–3 local revealable hints:
1. directional cue;
2. relevant principle/representation;
3. micro-example or partial step.

Hints are client-side reveals and do not create dialogue turns.

## `conceptual_conflict`

Use only when evidence supports a stable incorrect rule/model.

Compact sequence:
`learner rule -> one prediction -> counterexample -> reconstruction`

Prefer prediction/reveal in a local interactive block so the learner does not wait for another
agent round-trip.

Do not humiliate the learner or frame errors as personal deficiencies.

## `worked_example_fade`

Use for novices or stalled progress.

Choose one:
- completed analogous micro-example;
- partial solution with one missing step;
- full worked micro-example followed by a later independent check.

As evidence improves, remove steps rather than adding more explanation.

## `targeted_explanation`

Use when:
- the learner explicitly requests it;
- prerequisites are missing;
- repeated struggle is no longer productive;
- asking another question would not change the support policy.

Explain only the missing relation, not the whole lecture again.

## `teach_back`

Use sparingly at checkpoints when an explanation can reveal causal structure.

Best prompts:
- "为什么这个条件不能删？"
- "如果我是刚学的人，你会怎么解释 X 导致 Y？"

Avoid ritual teach-back after every concept.

## `transfer_check`

Use at natural checkpoints.

Good:
- new surface context;
- boundary case;
- classify a novel example;
- explain a failure mode.

Do not count a just-assisted item as independent evidence.

## `learner_model_challenge`

Triggered by an explicit learner event such as:
- `我不同意`
- `让我证明`

Generate one discriminative task whose result could revise the learner model.

Do not ask for learner-model negotiation during ordinary flow.
