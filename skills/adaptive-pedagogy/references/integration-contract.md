# Integration with existing Lingxi Skills

## Before personalized teaching

1. `lesson-intro` and `interactive-lecture-deck` may start in parallel from the same curriculum
   context; neither waits for the other.
2. Stream whichever preparation artifact is ready first, then continue with the other artifact when
   available.
3. Run `adaptive-pedagogy(mode=preflight)` independently as a cache producer; it must not block the
   first learner-facing artifact.

## Personalized phase

Only `adaptive-pedagogy` is a required student-facing pedagogical Skill in the personalized loop.
Use a Supervisor with manager-as-tools boundaries rather than peer-to-peer handoffs.

It may:
- answer in text itself;
- request `interactive-visual-explainer` as a non-blocking artifact;
- rarely request a remedial `interactive-lecture-deck` as a non-blocking artifact;
- emit background data for `learner-state-reflector`.

Each learner turn should have exactly one learner-facing writer. Structured assessor data and
background artifacts are inputs or sidecars, not additional chat responses.

## Do not register these v0.1 Skills on the blocking path

- `student-model-builder`
- `productive-struggle`
- `conceptual-conflict`
- `epistemic-calibration`
- `teach-back`
- `learner-model-negotiation`

Their pedagogical mechanisms now live in `strategy-kernel.md`.

## Why

Their boundaries are useful as *conceptual strategies* but too fine-grained as synchronous service
boundaries. Keeping them as separate blocking agents turns one educational decision into several
network/model round-trips and often generates redundant student questions.
