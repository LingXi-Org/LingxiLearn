"""Static V1 ownership, dependency and reachability gate."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "lingxilearn"


def module_name(path: Path) -> str:
    relative = path.relative_to(ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


FILES = {module_name(path): path for path in PACKAGE.rglob("*.py")}


def imported_modules(name: str, path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package = name if path.name == "__init__.py" else name.rpartition(".")[0]
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names if alias.name in FILES)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                try:
                    base = importlib.util.resolve_name("." * node.level + base, package)
                except (ImportError, ValueError):
                    continue
            if base in FILES:
                found.add(base)
            for alias in node.names:
                child = f"{base}.{alias.name}" if base else alias.name
                if child in FILES:
                    found.add(child)
    return found


def boundary_errors() -> list[str]:
    errors: list[str] = []
    for name, path in FILES.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        )
        if name.startswith("lingxilearn.api."):
            banned = ("sqlalchemy", "lingxilearn.store", "pathlib", "base64", "mimetypes")
            for imported in imports:
                if imported.startswith(banned):
                    errors.append(
                        f"{path.relative_to(ROOT)} imports forbidden API dependency {imported}"
                    )
        if (
            name.startswith("lingxilearn.application.")
            and name != "lingxilearn.application.container"
        ):
            banned = ("fastapi", "sqlalchemy", "lingxilearn.store.models")
            for imported in imports:
                if imported.startswith(banned):
                    errors.append(
                        f"{path.relative_to(ROOT)} imports forbidden application dependency {imported}"
                    )
        if name.startswith(("lingxilearn.domain.", "lingxilearn.ports.")):
            banned = ("fastapi", "sqlalchemy", "lingxilearn.api", "lingxilearn.store")
            for imported in imports:
                if imported.startswith(banned):
                    errors.append(f"{path.relative_to(ROOT)} imports infrastructure {imported}")
    return errors


def reachability_errors() -> list[str]:
    graph = {name: imported_modules(name, path) for name, path in FILES.items()}
    pending = ["lingxilearn.main", "lingxilearn.scheduler_worker", "lingxilearn.cli"]
    reached: set[str] = set()
    while pending:
        name = pending.pop()
        if name in reached or name not in graph:
            continue
        reached.add(name)
        pending.extend(graph[name] - reached)
        parts = name.split(".")
        reached.update(".".join(parts[:index]) for index in range(1, len(parts)))
    ignored = {name for name, path in FILES.items() if path.name == "__init__.py"}
    return [
        f"unreachable production module: {FILES[name].relative_to(ROOT)}"
        for name in sorted(set(FILES) - reached - ignored)
    ]


def baseline_errors() -> list[str]:
    errors: list[str] = []
    migrations = sorted((ROOT / "migrations" / "versions").glob("*.py"))
    if len(migrations) != 1 or migrations[0].name != "0001_initial_schema.py":
        errors.append(f"expected one 0001 migration, found {[path.name for path in migrations]}")
    forbidden = (
        "sqlite",
        "legacy-v0",
        "deterministic_fallback",
        "resource_refs",
        '"attachments"',
        "session_id",
        "class Session",
        "legacy",
        "fallback",
        "V0",
        "workspace_file_id",
        "workspace_file_title",
    )
    for path in PACKAGE.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        lowered = text.casefold()
        for token in forbidden:
            if token.casefold() in lowered:
                errors.append(f"{path.relative_to(ROOT)} contains removed baseline token {token}")
    return errors


def main() -> None:
    errors = [*boundary_errors(), *reachability_errors(), *baseline_errors()]
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"architecture gate passed ({len(FILES)} production modules)")


if __name__ == "__main__":
    main()
