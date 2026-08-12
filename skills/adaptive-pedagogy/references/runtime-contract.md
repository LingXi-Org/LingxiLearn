# Runtime contract

## Synchronous path

Normal path:
`student event -> adaptive-pedagogy -> render response`

Budget:
- one blocking pedagogical Skill call;
- at most one blocking external rendering Skill call, and only when necessary;
- zero dependence on `learner-state-reflector`.

## Background path

After rendering:
- enqueue `learner-state-reflector`;
- optionally build `interactive-visual-explainer`;
- store hint/choice/UI events.

The next synchronous call may use the most recent committed learner state, but it must also include
the current session's raw evidence so a delayed background update cannot block personalization.

## Preflight

While `interactive-lecture-deck` is being viewed, the host should *optionally* run:

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
