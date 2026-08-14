# Design rules

## Target types

- `retrieval`: recall the taught relation without copying a sentence.
- `near_transfer`: keep the relation but change the surface context slightly.
- `far_transfer`: apply the relation in a meaningfully new context only when the supplied material
  supports that application.
- `boundary_case`: test when a rule stops applying or which condition is necessary.
- `misconception_discriminator`: distinguish two plausible rules using one observable prediction.

Choose one main judgment per task. Prefer retrieval or near transfer when the learner has
`verification_debt`; reserve far transfer for a concept with demonstrated prerequisites.

## Candidate diversity

Candidates should differ in target type, surface context, or misconception discriminator. Do not
generate three paraphrases. Reject any candidate that relies on facts, examples, or diagrams absent
from `taught_content` and the supplied evidence.

## Public/internal split

`public_task` may contain only the prompt, options, response format, target type, and candidate ID.
Keep `grading_key`, explanations, keywords, assumptions, and rejection reasons internal. A host may
sanitize or render `public_task` without reading the internal candidate list.
