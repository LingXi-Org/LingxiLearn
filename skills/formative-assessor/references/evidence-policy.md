# Evidence policy

## Evidence states

- `demonstrated`: the supplied deterministic evidence shows the target relation in this event;
  never treat it as permanent mastery.
- `emerging`: partial or assisted evidence shows some usable relation but independence is not clear.
- `misconception_evidence`: a stable, rubric-supported incorrect rule is visible in the evidence.
- `needs_recheck`: strong help, a likely slip, or insufficient independent evidence leaves the next
  action uncertain.
- `not_observed`: no assessable evidence was supplied; use sparingly because the task normally
  requires at least one evidence reference.

## Confidence

Copy confidence only from `learner_reported` or `ui_captured`. If the task says `not_provided`,
return `confidence: null` and `confidence_basis: not_provided`. Tone, vocabulary, speed, and the
assessor's own impression are never confidence evidence.

## Policy signals

| Evidence | Signal |
| --- | --- |
| independent correct relation | `advance` or `transfer_check` |
| low-confidence likely slip | `minimal_cue` |
| learner asks for help but can continue | `progressive_hint` |
| stable incorrect rule with supported counterexample | `conceptual_conflict` |
| repeated failure or strong assistance | `worked_example_fade` or `transfer_check` |
| explanation requested or another question adds no value | `targeted_explanation` |
| no usable evidence | `retrieve_or_predict` |

The policy signal is an input to `adaptive-pedagogy`, not a message to the learner.
