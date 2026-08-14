# Quality gate

Before returning:

- confirm the task used a deterministic or explicitly structured evidence source;
- preserve every supplied `evidence_ref` used in the interpretation;
- do not infer confidence, psychology, mastery, or a learner profile;
- use `misconception_evidence` only when a stable incorrect rule is supported;
- use `next_probe_needed=true` for ambiguous, ungraded, or conflicting evidence;
- include `probe_reason` when a probe is needed;
- choose exactly one supported policy signal;
- keep all prose in Simplified Chinese;
- emit no learner-facing message, question, answer, or mandatory action;
- do not write state or call another Skill from the result.
