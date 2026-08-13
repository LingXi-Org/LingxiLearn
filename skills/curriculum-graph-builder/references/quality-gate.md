# Quality gate

Before returning a result, verify all of the following.

## Structure

- Output matches `curriculum-graph-builder-result.v1`.
- Every new node ID and edge ID is unique inside the patch and does not collide with supplied data.
- Every added edge points to an existing or newly added node.
- No self-loop is created unless the relation would genuinely require one; normally reject it.
- No duplicate `(source, target, relation)` edge is added.
- `base_revision` exactly matches the chosen existing graph revision, or is `null` for a new graph.

## Curriculum quality

- Each node represents one coherent curriculum entity.
- Labels are short and readable in Chinese.
- `importance` is curriculum importance, not mastery or recent frequency.
- Strict prerequisites use `prerequisite_of`; weak conceptual support uses `foundation_for`.
- `related_to` is rare and never used merely to force graph expansion.
- Optional hierarchy is defensible; coordinates are omitted unless requested or supplied.

## Learner-state quality

- `is_current` is independent from `learning_state`.
- Weak/mastery states originate only from structured learner signals or persisted state.
- No psychological, ability, motivation, or learning-style inference is made.
- Evidence IDs are preserved when provided.

## Traceability

- Every non-trivial added node/edge has at least one `source_refs` value when possible.
- `evidence_summary` cites only `source_id` values from the task.
- Unsupported claims are omitted rather than guessed.

## Safe merge

- Existing node and edge IDs are never changed.
- No destructive operations are emitted.
- Ambiguous cross-graph connections result in a new graph or warning, not an automatic merge.
