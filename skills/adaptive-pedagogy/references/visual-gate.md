# Visual gate

`interactive-visual-explainer` is optional.

## Use it when interaction is the cognition

Strong cases:
- learner should manipulate a parameter and observe a change;
- a geometric/spatial relation is difficult to verbalize;
- a state/algorithm trace benefits from stepping;
- conceptual conflict depends on seeing a counterexample;
- multiple representations need synchronized comparison.

## Do not use it when
- the task is simple retrieval;
- a one-line cue is enough;
- a static diagram would be decorative;
- creating the visual would add more wait than learning value.

## Request contract

```json
{
  "skill": "interactive-visual-explainer",
  "blocking": false,
  "brief": {
    "topic": "...",
    "learning_objective": "...",
    "interaction": "...",
    "predict_before_reveal": true,
    "capture_events": [
      "prediction",
      "hint_opened",
      "final_observation"
    ]
  },
  "fallback_text": "..."
}
```

If `blocking=false`, the host renders `fallback_text` immediately and attaches the HTML when ready.

Use `blocking=true` only if the required student action literally cannot be completed without the
interactive representation.
