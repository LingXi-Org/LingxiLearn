ARG DOCKER_REGISTRY=docker.m.daocloud.io
FROM ${DOCKER_REGISTRY}/oven/bun:1.3.14

WORKDIR /app

ARG NPM_REGISTRY=https://registry.npmmirror.com

COPY package.json bun.lock bunfig.toml ./
RUN bun install --ignore-scripts --registry ${NPM_REGISTRY}

CMD ["bun", "run", "dev"]
