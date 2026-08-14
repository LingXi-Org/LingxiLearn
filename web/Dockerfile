ARG DOCKER_REGISTRY=docker.m.daocloud.io
FROM ${DOCKER_REGISTRY}/oven/bun:1.3.14 AS builder

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

ARG DOCKER_REGISTRY=docker.m.daocloud.io
FROM ${DOCKER_REGISTRY}/oven/bun:1.3.14 AS runtime
ARG LINGXILEARN_VERSION=0.1.0
LABEL org.opencontainers.image.version="${LINGXILEARN_VERSION}"

WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 NEXT_STATIC_EXPORT=1
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["bun", "server.js"]
