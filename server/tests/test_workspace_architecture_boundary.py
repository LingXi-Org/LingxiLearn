from __future__ import annotations

import ast
from pathlib import Path

API_DIR = Path(__file__).parents[1] / "lingxilearn" / "api"


def test_workspace_router_is_a_small_domain_aggregator() -> None:
    source = (API_DIR / "workspace_routes.py").read_text(encoding="utf-8")
    assert len(source.encode()) < 2_000
    tree = ast.parse(source)
    assert not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in tree.body)


def test_workspace_domain_routes_remain_below_monolith_threshold() -> None:
    modules = sorted(API_DIR.glob("workspace_*_routes.py"))
    assert modules
    oversized = {
        module.name: module.stat().st_size for module in modules if module.stat().st_size >= 100_000
    }
    assert oversized == {}


def test_workspace_presentation_mappers_do_not_import_orm_models() -> None:
    mapper_dir = API_DIR / "mappers"
    violations: list[str] = []
    for module in mapper_dir.glob("*.py"):
        source = module.read_text(encoding="utf-8")
        if "store.models" in source or "sqlalchemy" in source:
            violations.append(module.name)
    assert violations == []
