ARG DOCKER_REGISTRY=accel.way2api.fun/docker.io
ARG BUN_VERSION=1.3.6
ARG NODE_VERSION=22
FROM ${DOCKER_REGISTRY}/oven/bun:${BUN_VERSION} AS builder

WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

ARG NPM_REGISTRY=https://registry.npmmirror.com
ARG NODE_OPTIONS=--max-old-space-size=768

ENV LINGXILEARN_API_ORIGIN=http://api:8000 \
    NODE_OPTIONS=$NODE_OPTIONS

COPY package.json bun.lock bunfig.toml ./
RUN bun install --frozen-lockfile --ignore-scripts --registry ${NPM_REGISTRY}
COPY . .

RUN rm -rf out .next && bun run build && test -f .next/standalone/server.js

FROM ${DOCKER_REGISTRY}/library/node:${NODE_VERSION}-bookworm-slim AS runtime
ARG LINGXILEARN_VERSION=1.0.0
ARG LINGXILEARN_REVISION
ARG LINGXILEARN_SOURCE=https://github.com/lingxi-org/LingxiLearn
LABEL org.opencontainers.image.version="${LINGXILEARN_VERSION}" \
      org.opencontainers.image.revision="${LINGXILEARN_REVISION}" \
      org.opencontainers.image.source="${LINGXILEARN_SOURCE}"

WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
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
