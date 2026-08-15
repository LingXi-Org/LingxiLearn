---
name: interactive-visual-explainer
description: >-
  Create a self-contained, offline interactive HTML explainer for concepts that are easier to understand through visual manipulation.
license: MIT
metadata:
  author: LingXi-Org
  version: 1.3.0
  display-name: 交互式可视化讲解
  display-description: 为适合通过观察和操作理解的概念生成可离线运行的交互式 HTML 讲解页面。
  output-language: zh-CN
  output-contract: interactive-visual-explainer-delivery.v1.2
  execution-mode: artifact-generation
  phase: teach
  critical-path: false
  learner-facing: artifact
  state-write-mode: none
  parallel-safe: true
  latency-class: background
  capabilities: content.visual
  status-line: 正在制作可视化讲解…
  provider: visual_explainer
  ownership: dedicated
  eval-suite: interactive-visual-explainer-v1
---

# Visual Explainer

## Role

Receive a concept from the orchestrating agent and produce one independently openable interactive
teaching artifact. It is a non-blocking sidecar requested by `adaptive-pedagogy`, not a competing
learner-facing chat writer. The caller must be able to render useful Chinese fallback text before
this artifact is ready. Make the conclusion live in the visual interaction, not only in prose. The
final delivery is exactly one `.html` file with no external requests, offline support, light/dark mode,
and print support. Do not routinely persist or deliver redundant intermediate files, such as
standalone image or PowerPoint exports of content already represented in the HTML. Temporary files
needed for an important design, validation, rendering, or compatibility check may be viewed or
written to the host; keep them ephemeral when possible and never include them in the final
delivery unless explicitly requested. All explanatory graphics in the final HTML must be authored
inline with SVG and/or CSS.

## Output language

All visible prose, labels, control text, explanations, accessibility text, captions, and delivery
notes must be Simplified Chinese. Preserve formulas, variable names, code identifiers, URLs, and
technical protocol tokens. Use Chinese even when the input is English unless a higher-priority
runtime policy explicitly overrides this rule.

## Defaults and intake

Read the supplied concept, audience, and emphasis. If fields are missing, use these defaults
without asking a follow-up question:

- concept: required; if absent, return Chinese `需求不完整` and do not guess;
- learning objective: “操作完之后，学习者应该明白 ___”;
- audience: familiar with an adjacent field but new to this concept;
- visual style: restrained academic paper style;
- interaction: choose one primary pattern from `references/interaction-patterns.md`;
- length: one and a half to three screens, one main interaction, and one or two supporting views;
- dependency: zero dependency. If a CDN is explicitly necessary, document an offline fallback.

## Authoring workflow

Follow this order:

1. Write the one-sentence Chinese learning objective before adding any element.
2. Identify one to three controllable variables. If no variable exposes a causal relation, use a
   static figure and Chinese explanation instead of forced interaction.
3. Choose the teaching pattern first, then the chart or SVG form. Read the relevant references.
4. Lay out coordinates in a 680-wide viewBox using `L=60 R=640 T=40 B=300`; budget Chinese text
   at 14 px per character and verify bounds and overlap.
5. Start from `assets/template.html`, inline `assets/lingxi.css` without changing its tokens, and
   keep every graphic in the final HTML as inline SVG and/or CSS. Do not routinely export a
   standalone image or presentation file; if a temporary file is necessary for a key check, use it
   only for that check and do not deliver it.
6. Assign colors by semantic role. Rerun both palette checks after every color change:

   ```text
   node scripts/validate_palette.js "<hex,hex,…>" --mode light
   node scripts/validate_palette.js "<hex,hex,…>" --mode dark
   ```

   Fix every FAIL before continuing.
7. Run `node scripts/check_page.js <page>.html`. Resolve every FAIL before delivery and explain
   any remaining WARN in the delivery note. This static check is the required artifact validation
   gate. Screenshots may be generated temporarily when a visual check is useful, but they are not
   required and are not delivery files.
8. Compare the result with `references/anti-patterns.md` before delivery.

## Non-negotiable design rules

1. Keep the artifact single-file, offline, and dependency-free by default.
2. Teach one thing in the first frame; do not require a control change to understand the premise.
3. Place each control below the figure it controls. Keep its caption between figure and controls.
4. Use one `render()` path to update the figure, numbers, annotations, and `aria-live` conclusion.
5. Round every displayed number and give sliders an explicit `step`.
6. Never use dual y-axes.
7. Keep color attached to entities, not rank; use no more than three colors per figure.
8. Give every SVG `<text>` element a `t`, `ts`, `th`, or `tn` class.
9. Select a dedicated dark palette; never create dark mode by inversion.
10. Use only 400/500 font weights, 0.5 px hairlines, no gradients or shadows, sentence case, and
    no emoji.
11. Deliver only the final self-contained HTML and the short delivery note. Any optional
    screenshots or other temporary validation artifacts must not be delivered.

## Required delivery note

Return a short Chinese note, not the full HTML, with:

```text
文件：<absolute path>
知识点：<one sentence>
学习目标：操作完之后，学习者应该明白 ___
主交互：<pattern> + <control and changed variable>
图形清单：图1 <description> / 图2 <description>
校验：validate_palette <light PASS / dark PASS>；check_page <FAIL count / WARN count>
补的假设：<assumptions>
已知取舍：<removed content and reason>
```

Read `assets/template.html` before implementation. Load only the directly relevant references,
including design tokens, SVG craft, interaction patterns, and anti-patterns. Treat the final HTML
and delivery note as Chinese artifacts.
