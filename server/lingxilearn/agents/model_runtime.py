"""Shared model-invocation plumbing for capability providers.

Extracted from the old coordinator graph unchanged, because the hard-won part
is not the routing that was deleted — it is this: streaming a child Agent
explicitly so its model and tool events reach the parent's event stream.
Calling a compiled Agent with ``ainvoke`` inside an ordinary graph node does not
make it a native subgraph, so without this the UI sees nothing while a
specialist works.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from lingxigraph import AIMessage, EventKind, HumanMessage, Runtime, ToolMessage

logger = logging.getLogger(__name__)
EVENT_CHANNEL = "agent_task"

RUNTIME_MODEL_ROLES = ("orchestrator", "goal_interpreter", "utility_evaluator", "learning_plan_decision")
"""Roles the loop itself needs, which are not capability providers."""


def model_roles() -> tuple[str, ...]:
    """Every agent role the host must build a model for.

    Derived from the provider registry rather than listed by hand, because a
    hand-written list is only correct until the next provider is added.
    """

    from .providers import load_all, names

    load_all()
    return tuple(sorted({*RUNTIME_MODEL_ROLES, *names()}))


class UnregisteredModelRole(KeyError):
    """A component asked for a per-role model the host never built."""


def agent_model(model: Any, role: str) -> Any:
    """Resolve the model instance for one agent role.

    Each role gets its own instance so its immutable prompt/tool prefix stays
    stable for the provider's prompt cache.

    A dict that is missing ``role`` raises rather than returning ``None``.
    Runtime control nodes are model-only and must never substitute a
    code-selected plan.
    """

    if isinstance(model, dict):
        resolved = model.get(role) or model.get("default")
        if resolved is None:
            raise UnregisteredModelRole(
                f"no model registered for agent role {role!r}; "
                f"known roles: {sorted(model)}"
            )
        return resolved
    resolver = getattr(model, "for_agent", None)
    if callable(resolver):
        return resolver(role)
    return model


def emit_agent_failure(
    runtime: Runtime[Any], agent_name: str, exc: BaseException
) -> None:
    """Emit one correctly attributed failure even when siblings run in parallel."""

    emit(
        runtime,
        "agent.failed",
        agent=agent_name,
        error_type=type(exc).__name__,
        message=str(exc) or type(exc).__name__,
    )


def emit(runtime: Runtime[Any] | None, event_type: str, **payload: Any) -> None:
    if runtime is None:
        return
    try:
        runtime.emit(EVENT_CHANNEL, {"type": event_type, **payload})
    except Exception:  # telemetry must never break a run
        logger.debug("agent telemetry failed: %s", event_type, exc_info=True)


def message_text(result: Any) -> str:
    messages = result.get("messages", []) if isinstance(result, dict) else []
    for message in reversed(messages):
        content = (
            message.content
            if isinstance(message, AIMessage)
            else getattr(message, "content", None)
        )
        if content:
            return str(content)
    return ""


def message_payload(message: Any) -> tuple[str, str]:
    """Return provider reasoning and visible content from a native message."""

    additional = getattr(message, "additional_kwargs", {}) or {}
    reasoning = ""
    if isinstance(additional, dict):
        for key in ("reasoning_content", "reasoning", "thinking"):
            if additional.get(key):
                reasoning = str(additional[key])
                break
    return reasoning, str(getattr(message, "content", "") or "")


async def invoke_agent(
    agent: Any,
    message: HumanMessage,
    runtime: Runtime[Any],
    *,
    agent_name: str,
    recursion_limit: int,
    tool_permissions: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Run a child Agent while forwarding its native runtime events.

    Calling a compiled Agent with ``ainvoke`` inside an ordinary graph node does
    not make it a native subgraph, so its model/tool events never reach the
    parent's stream.  Streaming the child explicitly keeps progressive skill
    disclosure observable without a second UI event implementation.
    """

    if runtime is None:
        return await agent.ainvoke(
            {"messages": [message]},
            {"recursion_limit": recursion_limit, "tool_permissions": list(tool_permissions)},
        )
    stream = getattr(agent, "astream", None)
    if not callable(stream):
        return await agent.ainvoke(
            {"messages": [message]},
            {
                "recursion_limit": recursion_limit,
                "tool_permissions": list(tool_permissions),
            },
        )

    config = {
        "recursion_limit": recursion_limit,
        "tool_permissions": list(tool_permissions),
    }
    latest: dict[str, Any] = {}
    reasoning_parts: list[str] = []
    content_parts: list[str] = []
    tool_calls: dict[str, dict[str, Any]] = {}
    model_started = 0.0
    tool_batch_started = 0.0

    def flush_text() -> None:
        if reasoning_parts:
            emit(
                runtime,
                "reasoning.delta",
                agent=agent_name,
                delta="".join(reasoning_parts),
            )
            reasoning_parts.clear()
        if content_parts:
            emit(
                runtime,
                "assistant.delta",
                agent=agent_name,
                delta="".join(content_parts),
            )
            content_parts.clear()

    try:
        async for mode, value in stream(
            {"messages": [message]},
            config,
            stream_mode=("events", "values"),
            context=getattr(runtime, "context", None),
            cancellation=getattr(runtime, "cancellation", None),
            subgraphs=True,
        ):
            if mode == "values":
                if isinstance(value, dict):
                    latest = value
                continue
            event = value
            if event.kind is EventKind.MESSAGE:
                envelope = event.data.get("value")
                native_message = (
                envelope[0] if isinstance(envelope, (tuple, list)) and envelope else None
            )
                if native_message is not None:
                    reasoning, content = message_payload(native_message)
                    replayed = (getattr(native_message, "additional_kwargs", {}) or {}).get(
                        "_reasoning_replay"
                    )
                    if reasoning and not replayed:
                        reasoning_parts.append(reasoning)
                    if content:
                        content_parts.append(content)
                    if sum(map(len, reasoning_parts)) + sum(map(len, content_parts)) >= 256:
                        flush_text()
                continue
            if event.kind is EventKind.NODE_STARTED and event.node == "agent":
                model_started = time.monotonic()
                emit(runtime, "model.started", agent=agent_name)
                continue
            if event.kind is EventKind.NODE_STARTED and event.node == "tools":
                tool_batch_started = time.monotonic()
                continue
            if event.kind is not EventKind.NODE_COMPLETED:
                continue
            update = event.data.get("update") or {}
            messages = update.get("messages", ()) if isinstance(update, dict) else ()
            if event.node == "agent":
                flush_text()
                response = messages[-1] if messages else None
                if isinstance(response, AIMessage):
                    for call in response.tool_calls:
                        call_payload = {
                            "id": call.id,
                            "name": call.name,
                            "args": dict(call.args),
                        }
                        tool_calls[call.id] = call_payload
                        emit(
                            runtime,
                            "tool.call.delta",
                            agent=agent_name,
                            calls=[call_payload],
                        )
                    usage = dict(response.usage or {})
                    if usage:
                        emit(runtime, "model.usage", agent=agent_name, usage=usage)
                    emit(
                        runtime,
                        "model.completed",
                        agent=agent_name,
                        duration_ms=round((time.monotonic() - model_started) * 1000, 2)
                        if model_started
                        else None,
                        response_metadata=getattr(response, "response_metadata", {}) or {},
                        additional_kwargs=getattr(response, "additional_kwargs", {}) or {},
                    )
                continue
            if event.node == "tools":
                duration_ms = (
                    round((time.monotonic() - tool_batch_started) * 1000, 2)
                    if tool_batch_started
                    else None
                )
                for result in messages:
                    if not isinstance(result, ToolMessage):
                        continue
                    call = tool_calls.get(result.tool_call_id, {})
                    emit(
                        runtime,
                        "tool.result",
                        agent=agent_name,
                        tool_call_id=result.tool_call_id,
                        name=result.name,
                        arguments=call.get("args", {}),
                        content=result.content,
                        status=result.status,
                        duration_ms=duration_ms,
                        additional_kwargs=result.additional_kwargs,
                        response_metadata=result.response_metadata,
                    )
        flush_text()
        return latest
    except Exception as exc:
        flush_text()
        emit(runtime, "model.failed", agent=agent_name, error=f"{type(exc).__name__}: {exc}")
        raise


__all__ = [
    "EVENT_CHANNEL",
    "RUNTIME_MODEL_ROLES",
    "UnregisteredModelRole",
    "agent_model",
    "emit",
    "emit_agent_failure",
    "invoke_agent",
    "message_payload",
    "message_text",
    "model_roles",
]
