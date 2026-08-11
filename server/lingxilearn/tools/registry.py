"""The tool registry.

Course packs name capabilities (``net.pcap.timeline``); the registry resolves
them to real Python.  The kernel's ``investigate`` node never imports a domain
module — adding 数据结构 or 操作系统 later means registering a new namespace,
not editing the graph.

Tools are declared with LingxiGraph's :func:`~lingxigraph.tool` so each one
carries a generated JSON Schema, which the LLM brains can reuse verbatim.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from lingxigraph import ToolSpec
from lingxigraph import tool as lingxi_tool


class ToolError(RuntimeError):
    """A tool failed in a way the learner should see, not a stack trace."""

    def __init__(self, message: str, *, code: str = "tool_failed") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ToolResult:
    name: str
    args: dict[str, Any]
    value: Any
    duration_ms: int
    ok: bool = True
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "args": dict(self.args),
            "value": self.value,
            "duration_ms": self.duration_ms,
            "ok": self.ok,
            "error": self.error,
        }


@dataclass
class ToolRegistry:
    specs: dict[str, ToolSpec] = field(default_factory=dict)

    def register(self, name: str, func: Callable[..., Any]) -> ToolSpec:
        # `lingxi_tool` turns the function into a frozen ToolSpec; the callable
        # stays reachable at `.func`, which is how we invoke it directly.
        spec = lingxi_tool(name=_schema_safe(name))(func)
        self.specs[name] = spec
        return spec

    def tool(self, name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator form. Returns the original function so it stays callable."""

        def decorate(func: Callable[..., Any]) -> Callable[..., Any]:
            self.register(name, func)
            return func

        return decorate

    def get(self, name: str) -> ToolSpec:
        try:
            return self.specs[name]
        except KeyError:
            raise ToolError(f"unknown tool: {name}", code="unknown_tool") from None

    def names(self, prefix: str = "") -> list[str]:
        return sorted(n for n in self.specs if n.startswith(prefix))

    def call(self, name: str, /, **kwargs: Any) -> ToolResult:
        """Run a tool, converting failures into a reportable result.

        Never raises for domain failures: a malformed capture is a teaching
        moment (and a UI branch), not a 500.
        """
        spec = self.get(name)
        started = time.perf_counter()
        try:
            value = spec.func(**kwargs)
        except ToolError as exc:
            return ToolResult(
                name=name,
                args=kwargs,
                value=None,
                duration_ms=_elapsed(started),
                ok=False,
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the learner as a tool failure
            return ToolResult(
                name=name,
                args=kwargs,
                value=None,
                duration_ms=_elapsed(started),
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
            )
        return ToolResult(name=name, args=kwargs, value=value, duration_ms=_elapsed(started))


def _elapsed(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _schema_safe(name: str) -> str:
    """Dotted ids are ours; function-calling APIs only accept ``[A-Za-z0-9_-]``."""
    return name.replace(".", "__")


registry = ToolRegistry()
"""Process-wide registry. Domain modules populate it on import."""


def load_builtin_tools() -> ToolRegistry:
    """Import the bundled domain toolboxes so they self-register."""
    from . import (
        knowledge,  # noqa: F401
        net,  # noqa: F401  (import side effect: registration)
    )

    return registry
