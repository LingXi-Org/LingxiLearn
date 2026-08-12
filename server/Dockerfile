# syntax=docker/dockerfile:1.7
# LingxiLearn API. Two stages so no build toolchain reaches the runtime layer.

FROM ghcr.io/astral-sh/uv:0.9.7 AS uvbin

FROM python:3.13-slim AS builder
COPY --from=uvbin /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml README.md ./
COPY lingxilearn ./lingxilearn
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv && uv pip install --no-cache .

FROM python:3.13-slim AS runtime
RUN apt-get update \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --gid 10001 lingxi \
 && useradd --uid 10001 --gid 10001 --create-home lingxi
WORKDIR /app
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LINGXILEARN_PACKS_DIR=/app/packs \
    LINGXILEARN_VAR_DIR=/app/var \
    LINGXILEARN_WEB_DIST=/app/web

COPY --from=builder --chown=10001:10001 /app/.venv /app/.venv
COPY --chown=10001:10001 lingxilearn ./lingxilearn
COPY --chown=10001:10001 alembic.ini ./alembic.ini
COPY --chown=10001:10001 migrations ./migrations

USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=7s --retries=5 --start-period=25s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=5)"

CMD ["uvicorn", "lingxilearn.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
