"""``learning_profile`` has exactly one writer, and this test is what keeps it true.

The state layer's central rule is that any agent may read the profile and none
may write it.  A comment cannot enforce that; this walks the AST of the whole
package and fails if any module outside the sanctioned writer mutates a
:class:`LearningProfile` row or constructs one.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "lingxilearn"

WRITER = PACKAGE / "store" / "profile_writer.py"
"""The single sanctioned writer."""

MODEL = "LearningProfile"

_SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def _modules() -> list[Path]:
    return sorted(path for path in PACKAGE.rglob("*.py") if "__pycache__" not in path.parts)


def _walk_scope(scope: ast.AST) -> Iterator[ast.AST]:
    """Walk ``scope`` without crossing into nested function bodies.

    Scoping matters: a repository module binds ``row`` to half a dozen
    different models in different methods.  A module-wide walk would treat one
    method's profile row as evidence that every other method's ``row`` is one
    too.
    """

    for child in ast.iter_child_nodes(scope):
        if isinstance(child, _SCOPE_NODES):
            continue
        yield child
        yield from _walk_scope(child)


def _scopes(tree: ast.Module) -> Iterator[ast.AST]:
    yield tree
    for node in ast.walk(tree):
        if isinstance(node, _SCOPE_NODES):
            yield node


def _mentions_model(node: ast.AST) -> bool:
    """True when the expression names ``LearningProfile`` anywhere inside it.

    Covers the realistic ways a row is obtained: ``LearningProfile(...)``,
    ``session.get(LearningProfile, ...)``, ``select(LearningProfile)...`` and
    the awaited forms of each.
    """

    return any(isinstance(child, ast.Name) and child.id == MODEL for child in ast.walk(node))


def _profile_locals(scope: ast.AST) -> set[str]:
    """Names actually bound to a ``LearningProfile`` row inside one scope.

    Deliberately binding-based rather than name-based: a variable merely
    *called* ``profile`` is usually the unrelated ``LearnerProfile`` document,
    and flagging it would make this guard noise instead of a rule.
    """

    names: set[str] = set()
    for node in _walk_scope(scope):
        if isinstance(node, ast.Assign) and _mentions_model(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if _mentions_model(node.annotation) or (
                node.value is not None and _mentions_model(node.value)
            ):
                names.add(node.target.id)
    return names


def test_only_the_profile_writer_constructs_profile_rows() -> None:
    offenders: list[str] = []
    for path in _modules():
        if path == WRITER:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == MODEL
            ):
                offenders.append(f"{path.relative_to(PACKAGE)}:{node.lineno}")
    assert not offenders, (
        "learning_profile rows may only be created by state/profile_writer.py; "
        f"found construction at {offenders}"
    )


def test_no_module_outside_the_writer_assigns_profile_attributes() -> None:
    offenders: list[str] = []
    for path in _modules():
        if path == WRITER:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for scope in _scopes(tree):
            locals_ = _profile_locals(scope)
            if not locals_:
                continue
            for node in _walk_scope(scope):
                if not isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                    continue
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if (
                        isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id in locals_
                    ):
                        offenders.append(
                            f"{path.relative_to(PACKAGE)}:{node.lineno} sets {target.attr}"
                        )
    assert not offenders, (
        "only state/profile_writer.py may mutate a learning_profile row; "
        f"found writes at {offenders}"
    )


def test_no_module_issues_bulk_profile_updates_or_deletes() -> None:
    """A bulk ``update()``/``delete()`` would bypass the writer entirely."""

    offenders: list[str] = []
    for path in _modules():
        if path == WRITER:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id not in {"update", "delete"}:
                continue
            for argument in node.args:
                if isinstance(argument, ast.Name) and argument.id == MODEL:
                    offenders.append(f"{path.relative_to(PACKAGE)}:{node.lineno}")
    assert not offenders, f"bulk update/delete of learning_profile bypasses the writer: {offenders}"


def test_the_guard_would_catch_a_real_violation() -> None:
    """A guard nobody has seen fail is not evidence of anything."""

    tree = ast.parse(
        "async def sneak(session):\n"
        "    row = await session.get(LearningProfile, 'x')\n"
        "    row.mastery = 1.0\n"
    )
    scope = next(node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef))
    assert _profile_locals(scope) == {"row"}

    clean = ast.parse(
        "async def fine(session):\n"
        "    row = await session.get(AgentTaskState, 'x')\n"
        "    row.runtime_status = 'PLANNING'\n"
    )
    clean_scope = next(node for node in ast.walk(clean) if isinstance(node, ast.AsyncFunctionDef))
    assert _profile_locals(clean_scope) == set()


def test_the_writer_refuses_changes_that_cite_no_evidence() -> None:
    """The guard is only meaningful if the writer itself demands evidence."""

    from lingxilearn.domain.learning_profile import ProfileDelta, UnsourcedProfileWrite

    try:
        ProfileDelta(
            learner_id="l",
            knowledge_point_id="kp",
            evidence_ids=[],
            source_agent="state_updater",
            mastery=1.0,
        )
    except UnsourcedProfileWrite:
        return
    raise AssertionError("ProfileDelta accepted a change with no evidence behind it")
