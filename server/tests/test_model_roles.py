"""Every agent role must resolve to a real model in the production shape.

This is the gap that let eleven roles ship resolving to ``None``. The unit tests
all hand a provider a fake model directly, so none of them exercised the thing
production actually builds: a ``{role: model}`` dict that has to contain a key
for every role anyone asks for.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path

import pytest

import lingxilearn
from lingxilearn.agents.model_runtime import (
    RUNTIME_MODEL_ROLES,
    UnregisteredModelRole,
    agent_model,
    model_roles,
)
from lingxilearn.agents.providers import load_all, names

PACKAGE = Path(lingxilearn.__file__).parent
VAR_DIR = PACKAGE.resolve().parents[1] / "var"


class _Sentinel:
    """Stands in for a chat model; identity is all these assertions need."""

    def __init__(self, role: str) -> None:
        self.role = role


def production_model_dict() -> dict[str, _Sentinel]:
    """The same shape ``Service.startup`` builds, without a network client."""

    return {role: _Sentinel(role) for role in model_roles()}


def _requested_roles() -> dict[str, list[str]]:
    """Every ``agent_model(x, "role")`` literal in the package, by role."""

    found: dict[str, list[str]] = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            name = (
                node.func.attr
                if isinstance(node.func, ast.Attribute)
                else getattr(node.func, "id", "")
            )
            if name not in {"agent_model", "_agent_model"} or len(node.args) < 2:
                continue
            role = node.args[1]
            if isinstance(role, ast.Constant) and isinstance(role.value, str):
                found.setdefault(role.value, []).append(
                    f"{path.relative_to(PACKAGE)}:{node.lineno}"
                )
    return found


def test_every_requested_role_is_one_the_host_builds() -> None:
    """The static half: no caller may ask for a role startup does not create."""

    built = set(model_roles())
    missing = {role: sites for role, sites in _requested_roles().items() if role not in built}
    assert not missing, (
        "these roles are requested but never built, so they resolve to None in "
        f"production: {missing}"
    )


def test_every_registered_provider_resolves_a_model() -> None:
    """The dynamic half: resolution against the real production dict."""

    load_all()
    models = production_model_dict()
    unresolved = []
    for role in names():
        try:
            if agent_model(models, role) is None:
                unresolved.append(role)
        except UnregisteredModelRole:
            unresolved.append(role)
    assert not unresolved, f"providers with no model in production: {unresolved}"


@pytest.mark.parametrize("role", RUNTIME_MODEL_ROLES)
def test_the_loop_s_own_roles_resolve(role: str) -> None:
    """The orchestrator degrading silently to deterministic ranking is the
    difference between an autonomous runtime and a scored lookup table."""

    assert agent_model(production_model_dict(), role) is not None


def test_each_role_gets_its_own_instance() -> None:
    """Sharing one instance across roles would break the prompt-cache prefix."""

    models = production_model_dict()
    instances = [agent_model(models, role) for role in model_roles()]
    assert len({id(item) for item in instances}) == len(instances)


def test_an_unregistered_role_raises_instead_of_returning_none() -> None:
    with pytest.raises(UnregisteredModelRole):
        agent_model(production_model_dict(), "a_role_nobody_built")


def test_no_model_configured_still_degrades_rather_than_raising() -> None:
    """With no API key the whole runtime degrades deterministically, by design."""

    assert agent_model(None, "orchestrator") is None


def test_model_roles_covers_every_provider_plus_the_loop() -> None:
    load_all()
    assert set(model_roles()) == {*RUNTIME_MODEL_ROLES, *names()}


@pytest.mark.asyncio
async def test_startup_builds_a_model_for_every_role_it_will_be_asked_for() -> None:
    """The integration check: the dict the real startup builds, not a stand-in.

    Everything above reasons about ``model_roles()``. This runs
    ``Service.startup`` with a credential present and asks the resulting dict
    for every role, which is the exact question production asks.
    """

    import os
    from uuid import uuid4

    from lingxilearn.application import ApplicationServices
    from lingxilearn.config import Settings

    path = VAR_DIR / f"test-roles-{uuid4().hex}.sqlite3"
    previous = os.environ.get("DS_API_KEY")
    os.environ["DS_API_KEY"] = "test-key-never-called"
    try:
        services = ApplicationServices(
            Settings(_env_file="", database_url=f"sqlite+aiosqlite:///./var/{path.name}")
        )
        assert services.settings.agents_configured, "the fixture failed to supply a credential"
        await services.db.create_all()
        await services.startup()
        try:
            assert services.agent_model, "startup built no per-role models"
            load_all()
            unresolved = [
                role
                for role in (*names(), *RUNTIME_MODEL_ROLES)
                if agent_model(services.agent_model, role) is None
            ]
            assert not unresolved, f"roles resolving to None after startup: {unresolved}"
        finally:
            await services.shutdown()
    finally:
        if previous is None:
            os.environ.pop("DS_API_KEY", None)
        else:
            os.environ["DS_API_KEY"] = previous
        path.unlink(missing_ok=True)  # noqa: ASYNC240 - teardown, not hot path


def test_every_module_in_the_package_imports() -> None:
    """A lazily imported module can carry a broken import for a long time.

    ``agents/curriculum_graph.py`` still imported the deleted ``agents.graph``
    and nothing noticed, because the only import of it is inside a provider
    function body.
    """

    failures: list[str] = []
    for module in pkgutil.walk_packages(lingxilearn.__path__, f"{lingxilearn.__name__}."):
        if ".cli" in module.name:
            continue
        try:
            importlib.import_module(module.name)
        except Exception as exc:  # noqa: BLE001 - the message is the assertion
            failures.append(f"{module.name}: {type(exc).__name__}: {exc}")
    assert not failures, "modules that cannot be imported: " + "; ".join(failures)
