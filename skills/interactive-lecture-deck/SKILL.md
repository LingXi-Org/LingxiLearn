---
name: interactive-lecture-deck
description: >-
  Create a fixed-size, self-contained HTML lecture deck with visual-first academic slides,
  structured `lecture.json` zoom data, anchored explanations, protected viewport behavior, a local
  presentation runtime, and an offline standalone build. Use for lessons, problem walkthroughs,
  course slides, zoomable HTML presentations, lecture manifests, and step-by-step teaching visuals.
  Use the bundled templates, schemas, references, runtime, build script, and validator. Chinese
  display name: 交互式讲解课件。Chinese display description: 生成视觉优先、可缩放、可离线运行的中文 HTML 课程课件及讲解数据。
license: MIT
compatibility: LingxiGraph Agent Skills runtime with Python 3
metadata:
  author: LingXi-Org
  version: 1.1.0
  display-name: 交互式讲解课件
  display-description: 生成视觉优先、可缩放、可离线运行的中文 HTML 课程课件及讲解数据。
  output-language: zh-CN
  output-contract: interactive-lecture-deck-result.v2.1
  execution-mode: artifact-generation
---

# Lecture Deck

## Role

Act as the interactive lecture-deck author in a multi-agent teaching system. Reconstruct supplied
teaching content into a visual narrative. Slides show structure; the explanation panel makes the
causal reasoning clear. Do not independently invent or fact-check lesson claims unless the caller
asks for that work. The primary learner-facing delivery is the built, offline `dist/lecture.html`.
The source slides, lecture data, runtime, and manifest remain available in the project workspace
when needed for authoring, build, alignment, and validation, but do not routinely duplicate or
return them as separate learner-facing exports.

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

## Mandatory loading order

1. Read this file.
2. Read `references/task-contract.md` and fill minor missing values by its defaults; do not ask
   the orchestrating agent a follow-up question.
3. Read `references/design-system.md`, `references/visual-authoring.md`, and
   `references/slide-authoring.md`.
4. Start from `assets/templates/slide-base.html` and finish `s01` opening first.
5. Read `references/lecture-data.md` and `references/zoom-contract.md` before writing
   `lecture.json`.
6. Copy `assets/runtime/index.html` to the project runtime directory.
7. Run `python3 scripts/build_standalone.py <project_dir>`.
8. Run `python3 scripts/validate_deck.py <project_dir> --strict`; standard delivery requires zero
   errors and zero warnings.

## Content and layout rules

1. Include an `opening` first slide, `closing` last slide, and `content` for every middle slide.
2. Keep every slide exactly 1280×720; let the runtime handle fitting.
3. Position direct content absolutely with explicit coordinates and stable anchor rectangles.
4. Give every content slide at least one `data-visual` object; never make a text-only body slide.
5. Use a conclusion-style title, minimal Chinese labels, and place detailed reasoning in the panel.
6. Draw the central relationship before adding labels. Choose a relation graph, process, coordinate
   chart, timeline, layered structure, comparison, formula map, or example decomposition.
7. Define two to four zoom anchors before writing page content.
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

Before authoring, create an internal outline with page role, one-sentence Chinese conclusion,
visual grammar, two to four zoom anchors, and the learner realization for each zoom. Compress long
source material into three to seven visual propositions rather than paginating paragraphs.

Use at least three pages. Default totals are 5–7 for one problem, 6–8 for one concept, and 8–12
for a lesson chapter. A requested `slideCount` includes opening and closing.

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

Run the build and strict validator above. If anchor geometry is content-driven, also run
`python3 scripts/measure_anchors.py <project_dir> --round 8`. Report total pages, content pages,
zoom-step count, primary standalone path, validation status, assumptions, and fallback items in
Chinese. Mention source/validation paths only when they help the caller use or inspect the project;
do not return redundant copies or scratch artifacts. The final published deck and all prose in its
manifest must be Chinese.
