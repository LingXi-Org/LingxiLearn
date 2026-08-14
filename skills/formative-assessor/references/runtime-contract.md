# Runtime contract

## Placement

Run after a deterministic judge/tool and only when the host cannot safely map the evidence itself:

```text
student event
  ↓
deterministic grader / tool
  ↓ evidence clear ───────────────→ adaptive-pedagogy
  ↓ evidence ambiguous
formative-assessor
  ↓ structured signal
adaptive-pedagogy
  ↓ guard → render one response
```

The normal path should not call this Skill. When it is called, it is the only conditional assessment
hop; it must return structured data and must not compete with `adaptive-pedagogy` for learner-facing
output.

## Failure behavior

If the Skill times out or fails, preserve the raw grader evidence and let the host use a conservative
`needs_recheck` fallback. Never block the learner on state reflection, visual generation, quiz
generation, or graph persistence.
