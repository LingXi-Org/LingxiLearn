# Runtime contract

## Prefetch path

```text
current learner task ─────────────→ adaptive-pedagogy → render response
             └── background → retrieval-practice-builder → cache
next learner event → validate cache relevance → use or discard
```

The cache is speculative. Discard it when the learner changes topic, supplies new evidence that
changes the support policy, or the selected task no longer matches the current objective.

## Failure behavior

If generation fails, preserve the raw evidence and continue the current teaching response. Do not
show a blank placeholder and do not retry synchronously. A result with insufficient evidence is a
valid no-cache outcome, not a reason to invent a question.
