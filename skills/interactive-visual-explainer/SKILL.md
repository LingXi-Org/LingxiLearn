---
name: interactive-visual-explainer
description: >-
  Create a self-contained, offline interactive HTML explainer for an algorithm, mathematical idea,
  physical mechanism, system, protocol, or other concept that is easier to understand by seeing
  and manipulating it. Use one to three meaningful controls, light/dark support, and an embedded
  explanation. Do not use for text-only answers, static reports, slides, or ordinary charts with
  no explanatory interaction. Chinese display name: 交互式可视化讲解。Chinese display description:
  生成零依赖、可离线打开的中文交互式 HTML 知识讲解页面。
license: MIT
compatibility: LingxiGraph Agent Skills runtime
metadata:
  author: LingXi-Org
  version: 1.0.0
  display-name: 交互式可视化讲解
  display-description: 生成零依赖、可离线打开的中文交互式 HTML 知识讲解页面。
  output-language: zh-CN
  output-contract: interactive-visual-explainer-delivery.v1
  execution-mode: artifact-generation
---

# Visual Explainer

## Role

Receive a concept from the orchestrating agent and produce one independently openable interactive
teaching page. Make the conclusion live in the visual interaction, not only in prose. The default
artifact is exactly one `.html` file with no external requests, offline support, light/dark mode,
and print support.

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
5. Start from `assets/template.html` and inline `assets/lingxi.css` without changing its tokens.
6. Assign colors by semantic role. Rerun both palette checks after every color change:

   ```text
   node scripts/validate_palette.js "<hex,hex,…>" --mode light
   node scripts/validate_palette.js "<hex,hex,…>" --mode dark
   ```

   Fix every FAIL before continuing.
7. Run `node scripts/check_page.js <page>.html`, render light and dark screenshots, and inspect
   them. The static checker cannot see DOM created at runtime.
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
11. Inspect rendered light and dark screenshots before delivery.

## Required delivery note

Return a short Chinese note, not the full HTML, with:

```text
文件：<absolute path>
知识点：<one sentence>
学习目标：操作完之后，学习者应该明白 ___
主交互：<pattern> + <control and changed variable>
图形清单：图1 <description> / 图2 <description>
校验：validate_palette <light PASS / dark PASS>；check_page <FAIL count / WARN count>
截图核对：亮色 ✓ 暗色 ✓
补的假设：<assumptions>
已知取舍：<removed content and reason>
```

Read `assets/template.html` before implementation. Load only the directly relevant references,
including design tokens, SVG craft, interaction patterns, and anti-patterns. Treat the final HTML
and delivery note as Chinese artifacts.
