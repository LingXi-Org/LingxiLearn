# syntax=docker/dockerfile:1.7
# Builds the static export. The result is copied into the API image's web root
# by compose, so production serves one process on one port.

FROM node:22-slim AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_API_BASE=
ARG NEXT_PUBLIC_LOGTO_ENDPOINT=
ARG NEXT_PUBLIC_LOGTO_APP_ID=
ARG NEXT_PUBLIC_LOGTO_RESOURCE=
ARG NEXT_PUBLIC_LOGTO_REDIRECT_URI=
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE \
    NEXT_PUBLIC_LOGTO_ENDPOINT=$NEXT_PUBLIC_LOGTO_ENDPOINT \
    NEXT_PUBLIC_LOGTO_APP_ID=$NEXT_PUBLIC_LOGTO_APP_ID \
    NEXT_PUBLIC_LOGTO_RESOURCE=$NEXT_PUBLIC_LOGTO_RESOURCE \
    NEXT_PUBLIC_LOGTO_REDIRECT_URI=$NEXT_PUBLIC_LOGTO_REDIRECT_URI
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY . .
RUN npm run build

# A tiny stage whose only job is to hand `out/` to the compose volume.
FROM busybox:1.37 AS dist
WORKDIR /dist
COPY --from=builder /app/out ./
CMD ["sh", "-c", "cp -r /dist/. /web/ && echo 'web assets published to /web' && ls /web"]
