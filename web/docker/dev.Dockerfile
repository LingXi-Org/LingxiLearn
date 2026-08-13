ARG DOCKER_REGISTRY=docker.m.daocloud.io
FROM ${DOCKER_REGISTRY}/oven/bun:1.3.14

WORKDIR /app

ARG NPM_REGISTRY=https://registry.npmmirror.com

COPY package.json bun.lock bunfig.toml ./
COPY packages ./packages
COPY apps/sim/package.json ./apps/sim/package.json

RUN bun install --ignore-scripts --registry ${NPM_REGISTRY}

CMD ["bun", "run", "--cwd", "apps/sim", "dev"]
