ARG DOCKER_REGISTRY=docker.m.daocloud.io
FROM ${DOCKER_REGISTRY}/oven/bun:1.3.14 AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
ARG NPM_REGISTRY=https://registry.npmmirror.com
ARG NEXT_PUBLIC_API_BASE=
ARG NEXT_PUBLIC_LINGXI_IDENTITY_ISSUER=
ARG NEXT_PUBLIC_LINGXI_IDENTITY_CLIENT_ID=
ARG NEXT_PUBLIC_LINGXI_IDENTITY_RESOURCE=
ARG NEXT_PUBLIC_LINGXI_IDENTITY_REDIRECT_URI=
ARG NEXT_PUBLIC_LINGXI_IDENTITY_SCOPE=
ARG DATABASE_URL=postgresql://build:build@localhost:5432/build
ARG NEXT_PUBLIC_APP_URL=http://localhost:8080
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE \
    NEXT_PUBLIC_LINGXI_IDENTITY_ISSUER=$NEXT_PUBLIC_LINGXI_IDENTITY_ISSUER \
    NEXT_PUBLIC_LINGXI_IDENTITY_CLIENT_ID=$NEXT_PUBLIC_LINGXI_IDENTITY_CLIENT_ID \
    NEXT_PUBLIC_LINGXI_IDENTITY_RESOURCE=$NEXT_PUBLIC_LINGXI_IDENTITY_RESOURCE \
    NEXT_PUBLIC_LINGXI_IDENTITY_REDIRECT_URI=$NEXT_PUBLIC_LINGXI_IDENTITY_REDIRECT_URI \
    NEXT_PUBLIC_LINGXI_IDENTITY_SCOPE=$NEXT_PUBLIC_LINGXI_IDENTITY_SCOPE \
    DATABASE_URL=$DATABASE_URL \
    NEXT_PUBLIC_APP_URL=$NEXT_PUBLIC_APP_URL \
    NEXT_STATIC_EXPORT=1
COPY package.json bun.lock bunfig.toml ./
COPY apps/sim/package.json apps/sim/package.json
COPY packages packages
# The Sim workspace is assembled from a large set of local packages. Docker
# copies the package manifests before the source tree, so Bun must resolve the
# workspace graph after those manifests are staged; a frozen install rejects
# the generated lock metadata even when the dependency set is valid.
RUN bun install --ignore-scripts --registry ${NPM_REGISTRY}
COPY . .
# Use Bun's `run --cwd` form. The previous argument order only printed Bun's
# help text and exited successfully, allowing a stale static export to be
# published by the dist stage.
RUN rm -rf apps/sim/out apps/sim/.next \
  && bun run --cwd apps/sim build \
  && test -f apps/sim/out/index.html

ARG DOCKER_REGISTRY=docker.m.daocloud.io
FROM ${DOCKER_REGISTRY}/library/busybox:1.37 AS dist
WORKDIR /dist
COPY --from=builder /app/apps/sim/out ./
CMD ["sh", "-c", "cp -r /dist/. /web/ && echo 'Sim/Lingxi assets published to /web' && ls /web"]
