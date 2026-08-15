ARG DOCKER_REGISTRY=accel.way2api.fun/docker.io
ARG BUN_VERSION=1.3.14
ARG NODE_VERSION=22-bookworm-slim

# Use Bun only to materialize the existing bun.lock dependency graph. The app
# declares Node >=22.19 and restored server routes rely on Node worker_threads
# APIs during `next build` page-data collection, so build and runtime stay on
# Node instead of executing Next.js under Bun.
FROM ${DOCKER_REGISTRY}/oven/bun:${BUN_VERSION} AS deps

WORKDIR /app
ARG NPM_REGISTRY=https://registry.npmmirror.com
COPY package.json bun.lock bunfig.toml ./
RUN bun install --ignore-scripts --registry ${NPM_REGISTRY}

FROM ${DOCKER_REGISTRY}/node:${NODE_VERSION} AS builder

WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

# Build-time values let Next.js safely evaluate server modules while collecting
# route data. Production Compose supplies the real public app URL at runtime.
ARG NEXT_PUBLIC_API_BASE=
ARG NEXT_PUBLIC_APP_URL=http://localhost:3000
ARG DATABASE_URL=postgresql://build:build@localhost:5432/build
ARG NODE_OPTIONS=--max-old-space-size=768

ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE \
    NEXT_PUBLIC_APP_URL=$NEXT_PUBLIC_APP_URL \
    DATABASE_URL=$DATABASE_URL \
    LINGXILEARN_API_ORIGIN=http://api:8000 \
    NEXT_STATIC_EXPORT=1 \
    NODE_OPTIONS=$NODE_OPTIONS

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN rm -rf out .next && node ./node_modules/next/dist/bin/next build && test -f .next/standalone/server.js

ARG DOCKER_REGISTRY=accel.way2api.fun/docker.io
ARG NODE_VERSION=22-bookworm-slim
FROM ${DOCKER_REGISTRY}/node:${NODE_VERSION} AS runtime
ARG LINGXILEARN_VERSION=0.1.0
LABEL org.opencontainers.image.version="${LINGXILEARN_VERSION}"

WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 NEXT_STATIC_EXPORT=1
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
