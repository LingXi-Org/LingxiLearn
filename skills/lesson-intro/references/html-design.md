# Single-File Lesson Page Design

This reference adapts a design-artifact workflow to a lesson doorway. The page is a small visual
experience, not a dashboard and not a complete course.

## Start with a private design brief

Before writing HTML, decide only what the topic needs:

- audience and reading situation;
- one-sentence narrative arc: scene → turn → question → next step;
- one visual metaphor that belongs to the concept;
- palette mood and contrast level;
- type scale and spacing rhythm;
- whether one small interaction improves understanding.

Do not expose this brief in the page. If the host accepts metadata, it may live there; otherwise keep
it in the agent's working context and move on.

## Page composition

Use a restrained reading path:

1. a quiet eyebrow or context cue, only if it helps;
2. one memorable `h1` that sounds like a question or a discovery;
3. a scene card, short story, or visual observation;
4. a single tension or “等等，为什么？” turn;
5. a question card that gives the learner something to hold;
6. a small forward invitation into the lesson.

These are compositional options, not mandatory fields. Remove any part that makes the page feel
like a form.

## Visual craft

- Choose a concept-specific motif: a slipping shoe for friction, a queue for latency, a shadow for
  perspective, a folding strip for topology. Build simple motifs with CSS, inline SVG, or text;
  never fetch an asset from the network.
- Establish hierarchy through size, weight, spacing, and contrast before adding decoration.
- Use one dominant surface and one accent color. Avoid generic neon gradients, random blobs, and
  decorative charts that do not teach anything.
- Keep line length comfortable, preserve generous whitespace, and make the smallest text readable.
- Give links, buttons, and expandable hints visible focus states and sensible labels.
- If there is motion, make it brief and purposeful. Respect `prefers-reduced-motion` and ensure the
  page still communicates when motion is disabled or JavaScript is unavailable.

## Self-contained implementation

Keep all style and behavior inside the HTML file. Do not load fonts, CSS, JavaScript, images,
analytics, iframes, or data from external URLs. Prefer semantic HTML and a small amount of CSS over
a large component framework. A static page with excellent typography is better than a fragile demo.

Use inline SVG only when it materially clarifies the idea. Add a text alternative or nearby prose so
the visual is never the sole carrier of meaning.

## Final visual pass

Open the generated file in a browser when the runtime provides a preview path. Check desktop and
narrow mobile widths, keyboard focus, reduced motion, and JavaScript-disabled reading. Look for
overflow, tiny type, weak contrast, awkward line breaks, and a visual that could belong to any topic.
Then remove one unnecessary element. A good lesson doorway usually becomes stronger when it has a
little more air and a little less furniture.
