---
name: lecture-hook
description: Research and create a short, evidence-grounded, curiosity-driven opening for a lesson or concept. Use when a teaching agent needs an engaging introduction, historical backstory, origin story, scientist/person story, real-world case, surprising fact, misconception, paradox, failure story, or "why should I care?" hook that must transition directly into the target knowledge point. Requires web research and source verification rather than invented anecdotes.
license: MIT
metadata:
  author: LingXi-Org
  output-contract: "lecture-hook-result.v1"
---

# Lecture Hook

Create a compelling *instructional doorway*, not a decorative story.

## Core standard

A successful hook must satisfy all four conditions:

- **Curiosity:** creates a concrete information gap, conflict, surprise, mystery, or unanswered question.
- **Relevance:** the learner must need the target concept to resolve the hook.
- **Grounding:** factual claims are traceable to fetched sources; uncertain anecdotes are labeled or rejected.
- **Brevity:** the opening is usually 45–120 seconds and hands off quickly to the lesson.

If an entertaining detail can be removed without changing why the target concept matters, treat it as a likely seductive detail and reject it.

## Inputs

Use whatever fields the caller supplies from [references/lecture-hook-task.schema.json](references/lecture-hook-task.schema.json). At minimum you need a `topic`. Infer minor missing fields conservatively; do not block on optional metadata.

Important context fields:

- `topic`: exact concept being taught.
- `learning_objective`: what learners should understand immediately after the lesson.
- `learner_level`: age / education level / prerequisite sophistication.
- `course_context`: where this concept sits in the larger lesson.
- `target_duration_sec`: preferred duration of the opening.
- `language`: narration language.
- `avoid`: themes or content to avoid.

## Workflow

### 1. Orient around the learning objective

Before searching, write a one-sentence internal target:

> "After this opening, the learner should be asking ______, and the target concept should be the natural way to answer it."

If no `learning_objective` is supplied, derive a minimal objective from the topic and course context.

### 2. Build a multi-angle search plan

Do not issue one generic query. Explore at least four of these angles, choosing the ones that fit the topic:

1. **Origin / historical need** — What problem existed before this idea?
2. **People / human conflict** — Who discovered, disputed, rejected, or popularized it?
3. **Failure / accident / limitation** — What broke, failed, or produced the need for the concept?
4. **Counterintuitive fact / paradox** — What outcome violates novice intuition?
5. **Everyday phenomenon** — Where does the learner encounter this without knowing the name?
6. **Modern application / stakes** — What current system, technology, or decision depends on it?
7. **Misconception** — What plausible belief does the concept overturn?
8. **Scale / extreme case** — What happens when the idea is pushed to an extreme?

Use [query patterns](assets/query-patterns.md) when useful.

### 3. Search broadly, then fetch selectively

Search first to map the terrain. Then fetch the most promising pages in full.

Minimum default research budget:

- 4 distinct search angles;
- 6 search results inspected;
- 3 full pages fetched;
- 2 independent sources supporting the selected hook's core factual premise.

This is a default, not a quota. Stop earlier only when a single primary/official source is decisive and the claim is straightforward. Continue longer when the story is disputed or source quality is weak.

### 4. Apply the source gate

Use [source-quality.md](references/source-quality.md).

Prefer, in order:

1. primary documents / original papers / official archives;
2. universities, museums, professional societies, government or standards bodies;
3. peer-reviewed scholarship and reputable scholarly reference works;
4. high-quality journalism or expert secondary sources;
5. tertiary summaries only for discovery, not as sole support for contentious claims.

Rules:

- A colorful historical anecdote needs two independent credible sources unless one is a strong primary source.
- A direct quote requires the actual source text; never quote from a search snippet alone.
- If reputable sources disagree, record the disagreement and either narrate it explicitly or choose another hook.
- Never turn "often attributed to" into "was invented by".

### 5. Build an evidence ledger

For every candidate fact likely to enter the narration, record:

- concise claim;
- source IDs;
- support status: `verified`, `qualified`, or `rejected`;
- confidence from 0 to 1;
- whether wording must preserve uncertainty.

Do not draft the final hook from untracked facts.

### 6. Generate three materially different candidate hooks

Default to 3 candidates, each from a different pattern when possible. See [hook-patterns.md](references/hook-patterns.md).

Good candidates have this shape:

1. **Immediate scene / puzzle / statement** (1–2 sentences)
2. **Specific tension or surprise**
3. **Learner-facing question**
4. **Bridge sentence** into the target concept

Do not explain the answer yet.

### 7. Score and reject

Score each candidate from 0–100 using:

- `lesson_alignment` — 30%
- `curiosity` — 20%
- `evidence_strength` — 20%
- `teachability` — 15%
- `learner_fit` — 10%
- `brevity` — 5%

Then apply penalties:

- −25 if the story is interesting but only loosely related to the objective;
- −30 if a central fact relies on one weak source;
- −20 if the transition requires a topic jump;
- reject outright if any central claim is fabricated, contradicted, or cannot be grounded.

The selected candidate should normally score at least 75. If none do, search again or switch hook pattern.

### 8. Seductive-detail test

Before finalizing, ask:

- Does every major detail earn its place by increasing the need to understand the target concept?
- Could the same story introduce ten unrelated topics just as easily?
- Does the bridge name the exact conceptual tension the lesson will resolve?

If the answer is unfavorable, cut details or reject the hook.

### 9. Produce the structured result

Return `lecture-hook-result.v1` matching [references/lecture-hook-result.schema.json](references/lecture-hook-result.schema.json).

Student-facing fields must be concise and source-free in prose. Put URLs and evidence in `research`, not inside the spoken narration unless the caller explicitly requests citations in the script.

Include:

- selected hook title;
- `opening`, `story`, `question`, and `transition`;
- optional visual cue for downstream PPT / visualization agents;
- 3 candidate summaries and scores;
- claim-to-source evidence ledger;
- source list;
- uncertainty / caveat flags;
- a short `why_this_hook_works` note for the teacher/orchestrator.

## Fallback ladder

When history is weak or boring, do not force it. Try in this order:

1. counterintuitive observation;
2. real-world failure or high-stakes case;
3. everyday phenomenon;
4. misconception;
5. thought experiment;
6. historical origin story.

The best hook is the one that makes the *concept necessary*, not the one with the oldest date.

## Special handling

### Mathematics

Prefer a concrete puzzle, visual contradiction, estimation failure, historical measurement problem, or "why this loss/definition?" tension. Avoid biography that never returns to the mathematics.

### Computer science / engineering

Prefer incidents, system failures, protocol design tradeoffs, scale problems, security surprises, or constraints that forced the design.

### Natural science

Prefer observation → anomaly → question, discovery stories with verified chronology, or phenomena learners can picture.

### Humanities / social science

Prefer primary-source tension, competing interpretations, historical decisions, or a small case that exposes the larger concept. Avoid flattening contested issues into a single colorful anecdote.

## Failure behavior

If trustworthy grounding cannot be established:

- do not fabricate;
- mark `status` as `insufficient_evidence`;
- return the best nonhistorical hook that can be grounded, or a clearly labeled thought experiment;
- explain the limitation in `warnings`.

## Reference files

- Source assessment: [references/source-quality.md](references/source-quality.md)
- Hook patterns: [references/hook-patterns.md](references/hook-patterns.md)
- Pedagogy constraints: [references/pedagogy.md](references/pedagogy.md)
- Runtime tool mapping: [references/tool-contracts.md](references/tool-contracts.md)
