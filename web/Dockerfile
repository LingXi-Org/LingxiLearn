ARG DOCKER_REGISTRY=accel.way2api.fun/docker.io
# Bun 1.3.14 crashes with SIGILL while Next collects page data on the CI
# runner. Keep the builder pinned to the stable 1.3.6 release until that Bun
# regression is resolved upstream. Bun is intentionally build-only: the
# production Next standalone server runs on Node's native HTTP runtime.
ARG BUN_VERSION=1.3.6
ARG NODE_VERSION=22
FROM ${DOCKER_REGISTRY}/oven/bun:${BUN_VERSION} AS builder

WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

ARG NPM_REGISTRY=https://registry.npmmirror.com
ARG NEXT_PUBLIC_API_BASE=
ARG NODE_OPTIONS=--max-old-space-size=768

ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE \
    LINGXILEARN_API_ORIGIN=http://api:8000 \
    NEXT_STATIC_EXPORT=1 \
    NODE_OPTIONS=$NODE_OPTIONS

COPY package.json bun.lock bunfig.toml ./
RUN bun install --ignore-scripts --registry ${NPM_REGISTRY}
COPY . .

RUN rm -rf out .next && bun run build && test -f .next/standalone/server.js

FROM ${DOCKER_REGISTRY}/library/node:${NODE_VERSION}-bookworm-slim AS runtime
ARG LINGXILEARN_VERSION=2.0.0
LABEL org.opencontainers.image.version="${LINGXILEARN_VERSION}"

WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 NEXT_STATIC_EXPORT=1
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000

# Probe the same Next rewrite path used by browser API/auth traffic. This makes
# a stuck standalone proxy visible as an unhealthy container instead of leaving
# the web process looking healthy while /api/* and /auth/* requests hang.
HEALTHCHECK --interval=30s --timeout=8s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/ready',{signal:AbortSignal.timeout(5000)}).then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
