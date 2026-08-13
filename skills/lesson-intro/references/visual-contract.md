# Lesson Intro Visual Contract

This contract adapts the shared `interactive-visual-explainer` visual language and the
`interactive-lecture-deck` composition discipline to a single responsive lesson doorway.

## 1. Composition

- Treat the page as an editorial opening, not a dashboard, blog post, or stack of rounded cards.
- Use a 12-column mental grid on wide screens: generous outer margin, a large left text field, and
  one dominant right-side or full-width visual. Collapse to one column only below the mobile break.
- The first frame must already communicate the scene and tension without requiring interaction.
- Use one conclusion-shaped or question-shaped `h1`, one short lead, one main visual, one figure
  caption, and one forward question. Remove any block that does not sharpen the concept.
- Let the visual occupy roughly half of the first viewport. Do not bury it below a long prose column.
- A single bottom rule and a small course/chapter note are preferred to a footer card.

## 2. Canonical tokens

Inline these tokens in the final HTML or use their exact equivalents. Do not invent a parallel color
system for a one-off page:

```css
:root {
  --paper:#fbfaf7; --surface:#ffffff; --sunken:#f4f2ec;
  --ink-1:#23231f; --ink-2:#5f5e5a; --ink-3:#8a8880;
  --rule:rgba(35,35,31,.14); --rule-strong:rgba(35,35,31,.30);
  --accent:#534ab7;
  --c1:#7f77dd; --c1-fill:#eeedfe; --c1-ink:#3c3489;
  --c2:#1d9e75; --c2-fill:#e1f5ee; --c2-ink:#085041;
  --c3:#d85a30; --c3-fill:#faece7; --c3-ink:#712b13;
  --font-serif:"Songti SC","Source Han Serif SC","Noto Serif SC","SimSun",Georgia,serif;
  --font-sans:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;
  --font-mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
```

Add explicit dark-mode values for `--paper`, `--surface`, `--sunken`, `--ink-*`, `--rule-*`,
`--accent`, and every color used in the visual. Never implement dark mode by inversion.

## 3. Type and surface rules

- Use the serif stack for the display title (`50–58px`, weight `500`) and the sans stack for lead
  (`20–22px`), body (`17–19px`), caption/note (`13–15px`), and controls.
- Use only weights `400` and `500`. Establish emphasis with scale, whitespace, and semantic color.
- Use the mono stack for numbers, formulas, and small index labels.
- Use hairline rules (`0.5px`) for dividers and SVG structure. Reserve `2px` for one selected or
  active state.
- Use only `4px`, `8px`, and `12px` radii. No shadows, gradients, glow, blur, glass, or giant pills.
- Keep a flat paper/surface relationship. A dark accent panel is acceptable only when it carries the
  question, not as a generic card treatment.

## 4. Visual grammar

- Every explanatory graphic belongs inside a `<figure>` with a `<figcaption>` that states what the
  figure reveals, not a repetition of the title.
- Prefer inline SVG/CSS diagrams over decorative illustrations. Use `viewBox="0 0 680 H"`, keep
  content inside x=`40..640`, and leave at least 40px safety space.
- Every SVG `<text>` must carry one of `t`, `ts`, `th`, or `tn`; add `<title>` and `<desc>` when the
  SVG conveys the main idea.
- Use no more than three semantic colors in one visual. Color identifies entities or states; it
  does not encode rank or decoration. Pair color with labels or geometry.
- Draw the relation first, then add labels. Prefer direct labels over a large detached legend.
- Do not use 3D, ornamental particles, random blobs, fake device mockups, or a generic hero
  illustration. The visual must explain the question's mechanism or boundary.

## 5. Interaction and accessibility

- Static is the default. Add one native control only when it exposes a causal relation.
- Put controls directly below the figure they change; include a visible value, a reset, and one
  `aria-live="polite"` sentence. The initial state must teach the basic case.
- Make the artifact useful with JavaScript disabled. Never hide the key conclusion in hover state.
- Support narrow screens, keyboard focus, `prefers-reduced-motion`, and print. Avoid viewport-sized
  typography that causes wrapping drift.

## 6. Final visual pass

Before delivery, inspect the first viewport at desktop and narrow mobile widths. Check that the title,
visual, caption, and question form one reading path; there is no accidental card grid, overflow,
weak-contrast label, or excessive empty gap. Run the shared palette checker for any changed semantic
colors and run `scripts/validate_output.py`.
