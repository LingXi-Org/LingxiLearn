# LingxiLearn web

This directory is the single Next.js frontend. It is intentionally not a
workspace, package collection, or Sim server runtime.

- `app/` contains public product pages, the LingxiIdentity callback, and the
  `/workspace/lingxi/...` conversation routes.
- `components/ui-kit/` is the shared visual language reused by product pages
  and the conversation surface.
- `lib/lingxi/` contains the REST/SSE client, event adapter, artifact views,
  and small API wire types.
- `content/` contains the public blog and library source.

Use Bun from this directory:

```text
bun run dev
bun run type-check
bun run build
```

The development Compose file bind-mounts this directory. The production
Compose file builds the static `out/` directory and serves it from the small
FastAPI runtime image.
