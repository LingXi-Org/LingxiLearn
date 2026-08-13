---
name: lesson-intro
description: >-
  Directly create a warm, self-contained Chinese HTML lesson opening from the supplied topic and
  curriculum context. Use when a learner needs a compact scene, puzzle, misconception, or question
  that makes a target concept worth learning; do not browse the web or aggregate search results.
license: MIT
metadata:
  author: LingXi-Org
  version: 4.2.0
  display-name: 课程引入
  display-description: 基于已有课程上下文直接生成自然有趣的课程开场 HTML，不联网搜索或聚合检索结果。
  output-language: zh-CN
  output-contract: lesson-intro-html.v1
  execution-mode: direct-editorial-html
  phase: prepare
  critical-path: true
  learner-facing: artifact
  state-write-mode: none
  parallel-safe: true
  latency-class: interactive
  eval-suite: lesson-intro-v1
---

# Lesson Opener

## Role

Create one small, delightful learning page—not a research report, dashboard, debug log, candidate
set, or agent handoff. This preparation artifact may run in parallel with
`interactive-lecture-deck` from the same curriculum context; do not wait for the deck or invoke
another teaching Skill. The learner should see a concrete scene, feel a small moment of surprise,
and leave with one question that makes the target concept worth learning.

## Input boundary

Use the supplied topic, learning objective, course context, learner level, and caller constraints.
They are the complete content boundary for the opening. Do not browse, call web search/fetch tools,
inspect webpages, collect URLs, aggregate external results, or create a source/claim ledger. Do not
invent a specific historical event, quotation, statistic, current fact, named anecdote, or dialogue.
When the supplied context cannot support a factual hook, use a clearly framed observation, puzzle,
counterfactual, or thought experiment instead. Keep the claim modest and let the lesson answer the
question later.

Read `references/input-grounding.md` for the direct-generation evidence boundary,
`references/visual-contract.md` before authoring any HTML, and `references/hook-patterns.md` only
when choosing a hook pattern. `references/visual-contract.md` is the shared visual baseline adapted
from `interactive-visual-explainer` and `interactive-lecture-deck`.

## Output contract

Return one complete, self-contained HTML document. If the host accepts plain artifacts, return the
HTML directly. If the host requires an envelope, use the smallest useful JSON object with an `html`
string and optional `topic`, `status`, `warnings`, or `structured_data`. The status, when present,
is `ok`; lack of external research is never a reason to delay or fail a usable introduction.

`structured_data` may contain private input, editorial, rendering, or quality notes, but never search
results, URLs, source records, claims, query logs, or aggregated evidence. Never copy machine
metadata into the page.

## Direct generation workflow

1. Read the input topic, objective, context, learner level, duration, and avoid-list. If context is
   thin, choose a low-risk conceptual hook rather than trying to fill the gap with outside facts.
2. Choose one hook that can be written immediately: a puzzle, failure pattern, everyday observation,
   intuition trap, definition tension, scale shift, or a context-supplied scene. Do not generate or
   compare a candidate list.
3. Hold the private learning promise: “After this opening, the learner should want to know ___.”
   Keep it private or in optional machine metadata.
4. Draft a compact arc: scene or observation → surprising turn → one concrete question → natural
   bridge into the target concept. Keep the bridge honest: the page is an invitation, not the full
   lesson.
5. Build the page around one dominant, concept-specific figure. Prefer a relation diagram or
   comparison with inline SVG over a decorative illustration or a stack of cards.
6. Apply the shared visual contract: canonical tokens, serif display title, sans body, hairline
   rules, no gradients/shadows/glass, at most three semantic colors, and a deliberate dark mode.
7. Run the HTML quality gate, the shared palette checker when colors change, and
   `scripts/validate_output.py`.

## Editorial autonomy

- Prefer a specific, understandable moment over generic “this topic is important” language.
- Prefer a conclusion-shaped title, a large visual, and a short caption over multiple small content
  cards. The page should feel closer to an editorial opening slide than a dashboard.
- Use conversational Simplified Chinese, short paragraphs, concrete verbs, and restrained warmth.
- Match the level: novices get a concrete scene and one tension; advanced learners may get a tradeoff,
  boundary condition, or competing model already supported by the input.
- Do not turn the opening into a mini-lecture, fact list, biography, news summary, or source digest.
- Use only one central question. Every visible beat must create that question, sharpen its stakes, or
  point toward the target concept.

## Single-file HTML design

Follow `references/visual-contract.md` and then `references/html-design.md` for the visual craft
pass. The essential constraints are:

- return one complete `<!doctype html>` document with `<html lang="zh-CN">`, UTF-8 metadata, a
  meaningful `<title>`, and a real `<body>`;
- inline all CSS and JavaScript; do not use external fonts, stylesheets, scripts, images, embeds,
  analytics, or network requests;
- make the page readable on a phone and a desktop, with visible focus states and a
  `prefers-reduced-motion` fallback;
- use semantic headings and landmarks, one `h1`, at most two `h2` headings, short readable
  paragraphs, and at least one `figure` with a `figcaption`;
- make the dominant visual an inline SVG or CSS diagram that is already meaningful in the first
  frame; for SVG use a `viewBox` width of `680` and classes `t`, `ts`, `th`, or `tn` on every
  `<text>` element;
- keep the visible page compact: normally 180–420 Chinese characters and a 45–120 second read,
  but shorten or extend it when the idea genuinely calls for it;
- prefer a static page. Add at most one restrained interaction—such as revealing a hint or gently
  changing a diagram state—only when it clarifies the question;
- do not put URLs, search notes, source lists, scores, or diagnostic labels in the page;
- do not hide internal parameters in HTML comments, `data-*` attributes, or script variables.

## HTML firewall

The visible HTML must contain only finished learner-facing content. Do not include task IDs, mode
names, schema versions, JSON, YAML, field names, hook lists, candidate lists, scores, rankings,
confidence values, evidence IDs, source records, query terms, provider names, tool names, budgets,
retries, runtime limits, internal warnings, debugging notes, implementation notes, orchestration
notes, or development notes. Do not include “作为 AI”“本 Agent”“本 Skill”“系统将”“根据任务”
or “以下是生成结果”等 meta language. Do not add unsupported facts, fabricated dialogue, invented
quotes, or confident wording for disputed claims.

## Quality gates

Before returning:

1. Check that the page uses only the supplied context or clearly framed non-factual imagination;
   never compensate for missing context with web browsing or result aggregation.
2. Check that the page has no external asset, network dependency, hidden metadata, or internal
   implementation text and remains useful with JavaScript disabled.
3. Check that the page follows `visual-contract.md`: no gradients/shadows/blur, no arbitrary colors,
   no oversized radii, no decorative hero, no card grid, and a dominant explanatory visual.
4. Check that the opening creates curiosity, the target concept is necessary, and the ending hands
   off cleanly to the lesson.
5. Check that the page contains one main question, a concrete scene or observation, and no candidate
   comparison or research summary.
6. Validate the HTML itself, or the optional minimal envelope, with `scripts/validate_output.py`.

## Result shape

Return one self-contained HTML document. If an envelope is required by the host, `html` is the only
required field; `topic`, `status`, `warnings`, and direct-generation metadata are optional
conveniences. All visible prose and the HTML page must be Simplified Chinese. Keep formulas, code,
identifiers, and schema keys in their technical form only when they are part of the lesson content
or private machine metadata.
