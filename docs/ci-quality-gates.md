# V1 CI 质量门禁

`.github/workflows/v1-quality.yml` 是 V1 代码质量的唯一 CI 事实源。

## 后端

```bash
cd server
uv sync --all-extras --frozen
uv run python scripts/check_architecture.py
uv run python scripts/export_openapi.py --check
uv run ruff check lingxilearn tests scripts
uv run ruff format --check lingxilearn tests scripts
uv run pytest tests
```

测试必须使用迁移后的 PostgreSQL，并通过
`LINGXILEARN_TEST_DATABASE_URL` 提供 DSN。架构门禁拒绝 API/Application
依赖倒置违规、不可达生产模块、非唯一迁移和已删除能力标记。

## 前端

```bash
cd web
bun install --frozen-lockfile --ignore-scripts
bun run generate:api
git diff --exit-code -- shared/api/generated/schema.ts
bun run check
LINGXILEARN_API_ORIGIN=http://127.0.0.1:8000 bun run build
```

`bun run check` 覆盖生产与测试类型、Biome、Vitest、Knip production 和
dependency-cruiser。允许的依赖方向只有 `app → features → entities → shared`。

## 发布镜像

容器工作流只发布 `sha-<git-sha>` 标签。部署前必须确认 API 与 Web 镜像使用同一
SHA，OCI `revision` 标签等于该 SHA，并在空 PostgreSQL volume、空 `api-var`
volume 上完成迁移及 `/live`、`/ready` 检查。
