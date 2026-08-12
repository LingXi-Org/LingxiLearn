---
name: quiz-generator
description: >-
  Define and eventually generate structured knowledge-point assessment items from an intent,
  lesson-intro result, and interactive lecture deck result. Use for the difficult-knowledge
  subgraph quiz-generation stage, contract validation, public-snapshot sanitization, and future
  quiz authoring. This is an interface skeleton only; do not implement the generation model here.
---

# Knowledge Quiz Generator

## Scope

Provide the stable skill boundary for the future `quiz_generator` node. This initial skill defines
the input and output contracts only. Keep question generation, rubric design, and model/tool
selection out of this skeleton until the quiz skill is deliberately implemented.

## Input

Read [quiz-generation-input.schema.json](references/quiz-generation-input.schema.json). The
runtime must provide one JSON object with:

- `schema_version`: `quiz-generation-input.v1`
- `task_id`: the durable Agent Task ID
- `intent`: the extracted knowledge-point context
- `lesson_intro`: the complete `lesson-intro-result.v1` value
- `interactive_lecture_deck`: the complete `interactive-lecture-deck-result.v2` value

Treat the two upstream results as evidence for alignment. Do not invent facts that are absent from
the supplied context, and do not mutate either upstream result.

## Output

Read [quiz-generation-result.schema.json](references/quiz-generation-result.schema.json). The
internal result must validate as `quiz-generation-result.v1` and include stable question IDs,
question types, prompts, options where applicable, points, and internal grading fields.

The service, not the skill, owns one-shot submission enforcement and persistence. Before returning
the public snapshot, remove `answer`, `explanation`, `keywords`, rubric details, and any other
grading hints. The public snapshot contains only renderable question data.

## Not implemented yet

Do not add model prompts, web research, question-selection heuristics, grading algorithms, or HTML
rendering in this initialization. Those are future implementation work behind this contract.
