---
name: interactive-lecture-deck
description: >-
  Build a fixed-size, self-contained HTML lecture deck with visual slides, structured explanations, zoom data, and offline delivery.
license: MIT
metadata:
  author: LingXi-Org
  version: 1.4.0
  display-name: 交互式讲解课件
  display-description: 构建包含视觉化幻灯片、结构化讲解数据和离线交付能力的自包含 HTML 课程课件。
  output-language: zh-CN
  output-contract: interactive-lecture-deck-result.v2.1
  execution-mode: artifact-generation
  phase: prepare
  critical-path: true
  learner-facing: artifact
  state-write-mode: none
  parallel-safe: true
  latency-class: interactive
  default-blocking-hop-budget: "0"
  eval-suite: interactive-lecture-deck-v1
---

# Lecture Builder

## Role

Act as the interactive lecture-deck author in a multi-agent teaching system. Reconstruct supplied
teaching content into a visual narrative. This preparation artifact may run in parallel with
`lesson-intro`; do not invoke it as a fact-checker or wait for any external-research result. Slides
show structure; the explanation panel makes the causal reasoning clear. Do not independently invent
or fact-check lesson claims unless the caller asks for that work. The primary learner-facing delivery
is the built, offline `dist/lecture.html`.
The source slides, lecture data, runtime, and manifest remain available in the project workspace
when needed for authoring, build, alignment, and validation, but do not routinely duplicate or
return them as separate learner-facing exports.

## Fast path (default — prioritize artifact delivery)

Optimize for one useful, validated artifact from the supplied context. Unless the caller requests
`constraints.qualityMode: full`, use this path:

1. Read `references/task-contract.md` only if inputs or output paths are unclear. Otherwise use defaults.
2. Read only the minimum reference needed to write the current artifact; templates and design references
   are optional when a usable existing layout is available.
3. Make a compact outline and start authoring immediately. Page count, layout, and anchor detail may be
   chosen incrementally; do not pause for a candidate comparison or staged approval.
4. Scaffold/copy the runtime, write the smallest complete `lecture.json` and `manifest.json`, build the
   standalone artifact, then run a quick validation. Run strict validation and targeted repairs when
   practical; do not block delivery on non-critical warnings.

Use the full path only when the caller asks for pixel-level visual review or when the task has custom
style/density, content-driven anchors, complex protected-view geometry, or a validator-detected layout
risk. Full path adds `design-system.md`, `visual-authoring.md`, and `zoom-contract.md`; it may also run
`measure_anchors.py` and temporary browser/render checks.

### Fast-path quality kernel

- Keep `opening` first, `closing` last, and every middle page `content`.
- Put one conclusion and one dominant `data-visual` on each content page.
- Keep visible text near 100 equivalent Chinese/ASCII units and never above 140.
- Add one useful zoom point to a content page when it improves teaching; additional zooms are optional.
- Keep anchors reasonably sized and aligned with both `data-rect` and `lecture.json`; use the runtime's
  defaults when exact geometry is not important.
- Keep slides static, self-contained, offline, and free of scripts, external assets, animation, shadows,
  gradients, and heavyweight UI chrome.
- Preserve the runtime's protected-view, geometry-probe, final guard, and full-bleed behavior.
- Prefer `build_standalone.py` followed by validation before claiming delivery. If strict validation is
  unavailable or non-critical warnings remain, deliver the built artifact and report the limitation.

### v2 contract checklist (hard requirements)

Before staging `lecture.json`, check every item below. These are schema requirements, not style
preferences:

- Every anchor object has `id`, non-empty `label`, and `rect: {x,y,w,h}`. Do not omit `label` and do
  not use the old four-number rect array.
- Every step has `advance: "manual"`.
- Every `overview` step uses exactly the full-view camera shape `{ "mode": "fit" }`; it must not
  carry `anchorId`, `depth`, `scale`, or `focus`. Only a `zoom` step uses `camera.mode: "anchor"`.
- Every SVG `<text>` in every slide has one of the classes `t`, `ts`, `th`, or `tn`.

Run a final schema/strict validation after staging. If a generated file is incomplete, finish or
repair that source file before returning the receipt; do not claim a staged deck is ready from a
partial `lecture.json`.

## Output language

All slide titles, labels, panel prose, onboarding text, narration, manifest descriptions, and
delivery notes must be Simplified Chinese. Preserve formulas, code, identifiers, URLs, schema keys,
and file names in their original form. The output contract is `interactive-lecture-deck-result.v2.1`.

## Required output

Produce these aligned project artifacts as needed for authoring, building, and strict validation;
the final learner-facing delivery is `dist/lecture.html`:

| Artifact | Requirement |
| --- | --- |
| `slides/sNN.html` | One self-contained 1280×720 HTML slide per page; required source/validation artifact |
| `lecture.json` | Overview, zoom steps, anchors, highlights, and Chinese panels; required alignment data |
| `runtime/index.html` | The bundled local presentation runtime; required runtime/build artifact |
| `dist/lecture.html` | One offline HTML publication with all content inlined; primary learner-facing delivery |
| `manifest.json` | Artifact inventory and validation result; required project record, not a redundant export |

Do not generate standalone PNG/JPG images, PowerPoint/PPTX exports, or duplicate HTML/JSON copies
when the inline slide assets and `dist/lecture.html` already serve the purpose. Temporary files
needed for an important design, validation, rendering, or compatibility check may be viewed or
written to the host; keep them ephemeral when possible and do not include them in the delivery.
Never remove a required project artifact before the build and strict validator have completed.

## Reference loading and authoring order

1. Read this file.
2. Read `references/task-contract.md` only when needed to resolve a missing contract value; do not ask
   a follow-up question for ordinary omissions. Omitted `constraints.qualityMode` means `fast`.
3. Follow the fast path unless an escalation condition applies. Load only the directly relevant
   references and templates; load the full-path references conditionally.
4. Start from `assets/templates/slide-base.html`, finish the opening and closing skeletons, then batch
   author the content pages.
5. Read `references/lecture-data.md` before writing non-trivial `lecture.json`; for a minimal deck,
   follow the existing example/schema and avoid loading unrelated zoom references.
6. Use `scripts/init_project.py` for a new project when available, or copy `assets/runtime/index.html`
   into an existing project runtime directory.
7. Run `python3 scripts/build_standalone.py <project_dir>`.
8. Run `python3 scripts/validate_deck.py <project_dir>` when available. Use `--strict` for full quality
   mode or when the quick check reports contract errors. Run `measure_anchors.py` only for content-driven
   geometry or a detected anchor risk.

## Content and layout rules

1. Include an `opening` first slide, `closing` last slide, and `content` for every middle slide.
2. Keep every slide exactly 1280×720; let the runtime handle fitting.
3. Position direct content absolutely with explicit coordinates and stable anchor rectangles.
4. Give every content slide at least one `data-visual` object; never make a text-only body slide.
5. Use a conclusion-style title, minimal Chinese labels, and place detailed reasoning in the panel.
6. Draw the central relationship before adding labels. Choose a relation graph, process, coordinate
   chart, timeline, layered structure, comparison, formula map, or example decomposition.
7. Define one anchor when zoom is useful; use two to four only when the explanation genuinely benefits.
8. Make each zoom step explain one observation or causal relation; split steps when the panel is
   overloaded.
9. Keep slides self-contained: no network requests, no scripts in slides, and images only as
   inline SVG or `data:` URIs.
10. Keep page animation in the runtime, not in slide CSS.
11. Keep `lecture.json` anchors and HTML `data-anchor`/`data-rect` values exactly aligned.
12. Write panels as natural Chinese teacher explanations following observation → reason → meaning;
    do not read slide text aloud.
13. Preserve the runtime's spatial 3D transition, free-view layer, protected viewport solving,
    clean full-bleed interface, and first-frame onboarding contract.
14. Keep all schema-external values inside `extensions`; do not invent top-level fields.

## Visual outline workflow

Before authoring, create one internal outline with page role, one-sentence Chinese conclusion, visual
grammar, two to four zoom anchors, and the learner realization for each zoom. Compress long source
material into three to seven visual propositions rather than paginating paragraphs. Do not create or
compare multiple candidate outlines unless the caller explicitly requests alternatives.

Use at least three pages when the source supports it. Default totals are 5–7 for one problem, 6–8 for
one concept, and 8–12 for a lesson chapter, but a shorter complete deck is acceptable when speed or
source length calls for it. A requested `slideCount` includes opening and closing.

## Build, validation, and delivery

Use the standard project layout for the required build and validation artifacts:

```text
<project_dir>/
├── slides/s01.html
├── runtime/index.html
├── dist/lecture.html
├── lecture.json
└── manifest.json
```

Run the build and the quickest available validator. If anchor geometry is content-driven, also run
`python3 scripts/measure_anchors.py <project_dir> --round 8`; do not run it by default. Report total
pages, content pages, zoom-step count, primary standalone path, validation status, assumptions, and
fallback items in Chinese. Mention source/validation paths only when they help the caller use or
inspect the project; do not return redundant copies or scratch artifacts. The final published deck and
all prose in its manifest must be Chinese.
