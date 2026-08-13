ARG DOCKER_REGISTRY=docker.m.daocloud.io
FROM ${DOCKER_REGISTRY}/oven/bun:1.3.14 AS builder

WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

ARG NPM_REGISTRY=https://registry.npmmirror.com
ARG NEXT_PUBLIC_API_BASE=
ARG DATABASE_URL=postgresql://build:build@localhost:5432/build

ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE \
    DATABASE_URL=$DATABASE_URL \
    NEXT_STATIC_EXPORT=1

COPY package.json bun.lock bunfig.toml ./
RUN bun install --ignore-scripts --registry ${NPM_REGISTRY}
COPY . .

RUN rm -rf out .next \
  && bun run build \
  && test -f out/index.html

ARG DOCKER_REGISTRY=docker.m.daocloud.io
FROM ${DOCKER_REGISTRY}/library/busybox:1.37 AS dist

WORKDIR /dist
COPY --from=builder /app/out ./
CMD ["sh", "-c", "cp -r /dist/. /web/ && echo 'LingxiLearn web assets published to /web' && ls /web"]
