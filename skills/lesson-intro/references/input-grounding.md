# Direct Input Grounding

Use the caller-provided topic, learning objective, course context, learner level, and constraints
as the only content boundary. This Skill does not retrieve, verify, compare, or aggregate external
material.

## Safe hook choices

- Prefer a concrete observation, puzzle, intuition trap, or definition tension that follows from the
  supplied context.
- Use a real event, quotation, number, named person, current claim, or historical detail only when
  it is explicitly present in the supplied context and can be stated without extending it.
- When context is thin, switch to a clearly marked thought experiment or a question about the target
  concept. Do not fill the gap with a plausible-looking anecdote.
- Preserve uncertainty in the wording when the input itself is uncertain. Never turn a possibility
  into a definite claim.

## Direct-generation rule

Choose one supported hook and write the artifact immediately. Do not create a candidate list, search
plan, source ledger, result ranking, fact-check report, or failure state merely because external
material was not retrieved. The introduction succeeds when it creates a focused question that the
lesson can answer.

## Content boundary checklist

Before returning, confirm that:

1. each factual sentence is traceable to the supplied context or has been softened into an
   observation, question, or thought experiment;
2. the page has one main tension and one bridge to the target concept;
3. no external URL, search result, source record, citation bookkeeping, or aggregation metadata is
   emitted;
4. the learner-facing HTML contains only finished lesson content.
