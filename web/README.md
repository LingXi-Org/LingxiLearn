# LingxiLearn web

The frontend is a single Next.js application rooted directly in `web/`.

Development uses `docker-compose.dev.yml` from the repository root and mounts
`./web` into a Bun development container. Production uses the root
`docker-compose.yml`; the web image builds a static export and the FastAPI
service serves it.

The only application backend contract used by the conversation UI is the
LingxiGraph REST/SSE API in `lib/lingxi/`.
