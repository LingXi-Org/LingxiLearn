# CI 质量门禁

`Product quality gates` 是 PR 的代码质量事实源；container image 构建只验证镜像可构建，不能替代这些检查。门禁按层并行运行，避免维护新增文件容易漏掉的手写文件清单。

## Frontend production quality

在 `web/` 下运行：

```bash
bun install --frozen-lockfile
bun run test:chat
bun run test:unit:core
bun run type-check
bun run lint:production
bun run build
bun run check:auth-boundary
bun run check:quality-boundaries
bunx vitest run --config vitest.config.ts scripts/check-quality-boundaries.test.ts
```

生产 lint 覆盖 `app/`、`components/`、`hooks/`、`lib/`、`stores/`、`blocks/`、`tools/` 与 Next 顶层入口；测试文件、生成代码及预构建 bundle 不属于该 lint 的源码事实范围。新增生产文件默认进入检查。

## Backend static quality

在 `server/` 下运行：

```bash
uv sync --locked --extra dev
uv run --extra dev ruff check lingxilearn tests
uv run --extra dev mypy lingxilearn
```

## Backend core tests

在 `server/` 下运行：

```bash
uv run --extra dev pytest -q
```

全量后端 suite 是核心测试的单一事实源；trajectory backend 测试已包含其中，不再由另一份文件列表重复执行。

## Architecture and artifact boundaries

在仓库根目录运行：

```bash
bash scripts/test-workspace-boundaries.sh
bash scripts/check-workspace-boundaries.sh web
bash scripts/check-tracked-artifacts.sh
cd web && bun run check:native-primitives-boundary
```

这些检查阻止产品层重新依赖 `w/**` 私有模块、恢复已删除的 `@sim/*` alias、重新打开 TypeScript/Next 绕过开关、恢复 fake compatibility routes，以及提交 pytest/build 临时目录。
