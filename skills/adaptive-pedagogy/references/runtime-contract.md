# Runtime contract

## Synchronous path

Normal path:
`student event -> deterministic judge/tools -> adaptive-pedagogy -> guard -> render response`

Ambiguous-evidence path:
`student event -> deterministic judge/tools -> formative-assessor -> adaptive-pedagogy -> guard -> render response`

Budget:
- normal path: one blocking pedagogical Skill call;
- ambiguous path: at most one conditional blocking `formative-assessor` call, then one
  `adaptive-pedagogy` call;
- zero blocking visual, quiz, learner-state, or remedial-deck Skill calls;
- zero dependence on `learner-state-reflector`.

The only learner-facing writer on this path is `adaptive-pedagogy`:
`learner_facing_writer_count <= 1`.

## Background path

After the response is rendered:
- enqueue `learner-state-reflector`;
- optionally prefetch `retrieval-practice-builder`, `interactive-visual-explainer`, a remedial deck,
  or a quiz;
- store hint/choice/UI events.

The next synchronous call may use the most recent committed learner state, but it must also include
the current session's raw evidence so a delayed background update cannot block personalization.

## Preflight

Once curriculum context is available, the host may run this preflight in parallel with
`lesson-intro` and `interactive-lecture-deck`:

```json
{
  "mode": "preflight",
  "topic": "...",
  "learning_objective": "...",
  "taught_content": "...",
  "learner_state": {}
}
```

Cache:
- first post-lecture probe;
- likely misconception branch notes;
- visual briefs.

After a concept response, `retrieval-practice-builder` may add a next-task cache. The host must
discard it when the topic, learner evidence, or current support policy changes.

Discard the cache if the learner asks a different question or skips to another topic.

## UI events that count as evidence

- answer submission;
- hint reveal level;
- support-choice click;
- visual prediction;
- visual observation/selection;
- learner-model challenge.

These can personalize future support without requiring a chat utterance.

## Failure fallback

If background jobs fail:
- continue synchronous teaching;
- preserve raw events for later replay.

If visual generation fails:
- use `fallback_text`;
- never leave the learner waiting on a blank placeholder.
