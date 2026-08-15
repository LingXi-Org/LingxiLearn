ARG DOCKER_REGISTRY=accel.way2api.fun/docker.io
# Bun 1.3.14 crashes with SIGILL while Next collects page data on the CI
# runner. Keep the image pinned to the stable 1.3.6 runtime until that Bun
# regression is resolved upstream.
ARG BUN_VERSION=1.3.6
FROM ${DOCKER_REGISTRY}/oven/bun:${BUN_VERSION} AS builder

WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

ARG NPM_REGISTRY=https://registry.npmmirror.com
ARG NEXT_PUBLIC_API_BASE=
ARG DATABASE_URL=postgresql://build:build@localhost:5432/build
ARG NODE_OPTIONS=--max-old-space-size=768

ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE \
    DATABASE_URL=$DATABASE_URL \
    LINGXILEARN_API_ORIGIN=http://api:8000 \
    NEXT_STATIC_EXPORT=1 \
    NODE_OPTIONS=$NODE_OPTIONS

COPY package.json bun.lock bunfig.toml ./
RUN bun install --ignore-scripts --registry ${NPM_REGISTRY}
COPY . .

RUN rm -rf out .next && bun run build && test -f .next/standalone/server.js

ARG DOCKER_REGISTRY=accel.way2api.fun/docker.io
ARG BUN_VERSION=1.3.6
FROM ${DOCKER_REGISTRY}/oven/bun:${BUN_VERSION} AS runtime
ARG LINGXILEARN_VERSION=0.1.0
LABEL org.opencontainers.image.version="${LINGXILEARN_VERSION}"

WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 NEXT_STATIC_EXPORT=1
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["bun", "server.js"]
