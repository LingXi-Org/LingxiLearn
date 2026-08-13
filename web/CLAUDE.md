# LingxiLearn web notes

Keep the frontend root-only. New browser features belong in `app/`,
`components/`, or `lib/lingxi/`; do not reintroduce `apps/`, `packages/`,
Turbo tasks, Sim server routes, or browser-side database/auth code.

Use existing UI-kit components and the LingxiGraph adapter for new product
surfaces. Never render raw model reasoning: only the adapter's safe stage
summaries may be shown in the expandable reasoning component.
