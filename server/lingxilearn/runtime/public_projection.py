"""Project internal runtime events into Lingxi Mothership Stream V1 (issue #18).

A pure, synchronous mapping over the V0 event dicts that flow through the
service's persistence buffer.  For every V0 flush the service also runs this
projector and appends the resulting envelopes as ``protocol_version=1`` rows —
dual projection: the V0 stream keeps serving today's UI while V1 becomes the
contract the next frontend stage consumes.

Nothing here guesses identity: if a V0 event carries ``agent_run_id`` the V1
event is scoped to it; if it does not, the projector falls back to the span
registry populated by dispatcher-emitted span starts, and otherwise emits the
fact unscoped rather than inventing an id.
"""

from __future__ import annotations

import logging
from typing import Any

from ..contracts.mothership_stream_v1 import (
    EventScope,
    LingxiMothershipEventV1,
    LingxiMothershipStreamV1Encoder,
    StreamScope,
    TraceScope,
    now_iso,
    validate_public_payload,
)
from ..tools.public_projection import (
    display_title,
    is_known_tool,
    public_tool_params,
    public_tool_result,
)

logger = logging.getLogger(__name__)

RUN_TERMINAL_MAP = {
    "run.completed": "completed",
    "run.failed": "failed",
    "run.cancelled": "cancelled",
    "run.timed_out": "failed",
    "run.budget_exceeded": "failed",
    "run.ended": "completed",
}
TASK_TERMINAL_MAP = {
    "task.completed": "delivered",
    "task.failed": "failed",
    "task.cancelled": "cancelled",
}

_TOOL_ERROR_STATUSES = {"error", "failed"}


class PublicProjector:
    """Stateful V0 → V1 event projector for one execution."""

    def __init__(
        self,
        *,
        chat_id: str,
        execution_id: str,
        turn_id: str = "",
        stream_id: str = "",
        request_id: str = "",
    ) -> None:
        self._encoder = LingxiMothershipStreamV1Encoder()
        self._stream = StreamScope(
            chat_id=chat_id,
            turn_id=turn_id,
            execution_id=execution_id,
            stream_id=stream_id or execution_id,
        )
        self._trace = TraceScope(request_id=request_id, run_id=execution_id)
        self._seq = 0
        # Span registry: V0 agent name -> most recent agent_run_id, populated
        # from dispatcher-emitted lifecycle events carrying real identity.
        self._agent_runs: dict[str, str] = {}
        self._open_spans: set[str] = set()
        self._terminated = False

    # -- public API ---------------------------------------------------------

    @property
    def stream(self) -> StreamScope:
        return self._stream

    def set_turn(self, turn_id: str) -> None:
        if turn_id and turn_id != self._stream.turn_id:
            self._stream = StreamScope(
                chat_id=self._stream.chat_id,
                turn_id=turn_id,
                execution_id=self._stream.execution_id,
                stream_id=self._stream.stream_id,
            )

    def consume(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        """Map one V0 buffer event to zero or more V1 envelope dicts.

        Returns JSON-ready ``model_dump()`` dicts with ``seq=0``; the
        repository rewrites ``seq`` (and ``stream.executionId``) when it
        assigns the durable task sequence at append time.
        """

        kind = str(event.get("kind") or "")
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}
        agent = str(event.get("agent") or "")
        handler = getattr(self, f"_on_{kind.replace('.', '_')}", None) if kind else None
        envelopes: list[LingxiMothershipEventV1] = []
        if handler is not None:
            envelopes = [item for item in handler(event, payload, agent) if item is not None]
        else:
            envelopes = self._generic(event, payload, agent)
        out: list[dict[str, Any]] = []
        for envelope in envelopes:
            out.append(envelope.model_dump(mode="json", by_alias=True))
        return out

    # -- lifecycle handlers ---------------------------------------------------

    def _on_run_started(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        return [self._emit("run", {"status": "started", "executionId": self._stream.execution_id})]

    def _on_run_resumed(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        return [self._emit("run", {"status": "resumed", "executionId": self._stream.execution_id})]

    def _on_run_paused(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        interaction_id = ""
        for marker in payload.get("interrupts") or []:
            if isinstance(marker, dict) and marker.get("kind") == "interaction":
                interaction_id = str(marker.get("interaction_id") or "")
                break
        # The public pause payload carries only the interaction identity —
        # never graph state, plan, or messages (issue #18 §5.8).
        body: dict[str, Any] = {"status": "checkpoint_pause", "executionId": self._stream.execution_id}
        if interaction_id:
            body["interactionId"] = interaction_id
        return [self._emit("run", body)]

    def _on_interrupt_raised(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        # Legacy untyped interrupts carry raw checkpoint payloads; project a
        # pause with no detail rather than leaking them. Typed interactions
        # arrive through interaction.requested instead.
        return self._on_run_paused(event, payload, agent)

    def _on_run_ended(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        return self._terminal_run("run.ended", payload)

    def _on_run_completed(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        return self._terminal_run("run.completed", payload)

    def _on_run_failed(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        return self._terminal_run("run.failed", payload)

    def _on_run_cancelled(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        return self._terminal_run("run.cancelled", payload)

    def _on_run_timed_out(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        return self._terminal_run("run.timed_out", payload)

    def _on_run_budget_exceeded(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        return self._terminal_run("run.budget_exceeded", payload)

    def _terminal_run(self, kind: str, payload: dict[str, Any]) -> list[LingxiMothershipEventV1]:
        if self._terminated:
            return []
        self._terminated = True
        status = RUN_TERMINAL_MAP[kind]
        events = [self._emit("run", {"status": status, "executionId": self._stream.execution_id})]
        complete_status = "delivered" if status == "completed" else status
        if complete_status != "cancelled":
            events.append(self._emit("complete", {"status": complete_status}))
        else:
            events.append(self._emit("complete", {"status": "cancelled"}))
        return events

    def _on_task_completed(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        return self._terminal_task("task.completed")

    def _on_task_failed(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        return self._terminal_task("task.failed", message=str(payload.get("message") or ""))

    def _on_task_cancelled(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        return self._terminal_task("task.cancelled")

    def _terminal_task(self, kind: str, *, message: str = "") -> list[LingxiMothershipEventV1]:
        if self._terminated:
            return []
        self._terminated = True
        events = [self._emit("error", {"message": message or "运行已结束", "fatal": True})] if kind == "task.failed" else []
        events.append(self._emit("complete", {"status": TASK_TERMINAL_MAP[kind]}))
        return events

    # -- agent span lifecycle -------------------------------------------------

    def _on_agent_started(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        agent_run_id = str(payload.get("agent_run_id") or "")
        if not agent_run_id:
            # Provider-emitted legacy start without dispatcher identity; do
            # not synthesize an id — register for later attribution only.
            return []
        if agent_run_id in self._open_spans:
            return []
        self._open_spans.add(agent_run_id)
        if agent:
            self._agent_runs[agent] = agent_run_id
        scope = EventScope(agent_run_id=agent_run_id)
        return [
            self._emit(
                "span",
                {
                    "kind": "agent",
                    "event": "start",
                    "agentRunId": agent_run_id,
                    "providerId": str(payload.get("provider") or payload.get("provider_id") or agent),
                    "displayName": str(
                        payload.get("display_name") or payload.get("agent_display_name") or agent
                    ),
                    "executionKind": str(payload.get("execution_kind") or "model"),
                    "capability": str(payload.get("capability") or ""),
                    "presentationRole": str(payload.get("presentation_role") or "supporting"),
                },
                scope=scope,
            )
        ]

    def _on_agent_completed(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        return self._end_span(event, payload, agent, "completed")

    def _on_agent_failed(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        status = "cancelled" if str(payload.get("status") or "") == "cancelled" else "failed"
        return self._end_span(event, payload, agent, status)

    def _end_span(
        self, event: dict[str, Any], payload: dict[str, Any], agent: str, status: str
    ) -> list[LingxiMothershipEventV1]:
        agent_run_id = str(payload.get("agent_run_id") or "")
        if not agent_run_id and agent:
            agent_run_id = self._agent_runs.get(agent, "")
        if not agent_run_id or agent_run_id not in self._open_spans:
            # A span end without a matching dispatcher start is a projection
            # gap, not a learner-visible fact.
            return []
        self._open_spans.discard(agent_run_id)
        return [
            self._emit(
                "span",
                {
                    "kind": "agent",
                    "event": "end",
                    "agentRunId": agent_run_id,
                    "status": status,
                },
                scope=EventScope(agent_run_id=agent_run_id),
            )
        ]

    # -- skill runs (dispatcher-owned ToolCallItems, issue #18 §4.6) ---------

    def _on_skill_started(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        skill_run_id = str(payload.get("skill_run_id") or "")
        if not skill_run_id:
            return []
        agent_run_id = str(payload.get("agent_run_id") or "")
        safe_params: dict[str, Any] = {"skillId": str(payload.get("skill_id") or "")}
        if payload.get("version"):
            safe_params["version"] = str(payload["version"])
        return [
            self._emit(
                "tool",
                {
                    "toolCallId": skill_run_id,
                    "toolKind": "skill",
                    "toolName": "lingxi.skill",
                    "displayTitle": str(payload.get("display_name") or payload.get("skill_id") or "技能"),
                    "status": "executing",
                    "safeParams": safe_params,
                },
                scope=EventScope(agent_run_id=agent_run_id, skill_run_id=skill_run_id),
            )
        ]

    def _on_skill_completed(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        return self._end_skill(payload, "success")

    def _on_skill_failed(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        return self._end_skill(payload, "error")

    def _end_skill(self, payload: dict[str, Any], status: str) -> list[LingxiMothershipEventV1]:
        skill_run_id = str(payload.get("skill_run_id") or "")
        if not skill_run_id:
            return []
        agent_run_id = str(payload.get("agent_run_id") or "")
        return [
            self._emit(
                "tool",
                {
                    "toolCallId": skill_run_id,
                    "toolKind": "skill",
                    "toolName": "lingxi.skill",
                    "displayTitle": str(payload.get("display_name") or ""),
                    "status": status,
                },
                scope=EventScope(agent_run_id=agent_run_id, skill_run_id=skill_run_id),
            )
        ]

    # -- text channels ----------------------------------------------------------

    def _on_agent_status(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        text = str(payload.get("text") or "")
        if not text:
            return []
        agent_run_id = str(payload.get("agent_run_id") or "") or self._agent_runs.get(agent, "")
        scope = EventScope(agent_run_id=agent_run_id) if agent_run_id else EventScope()
        # Host status lines are learner-safe narration, never model output.
        return [
            self._emit(
                "text",
                {"channel": "narration", "text": text, "source": "system" if not agent_run_id else "agent"},
                scope=scope,
            )
        ]

    def _on_agent_output(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        message = str(payload.get("message") or "")
        if not message:
            return []
        agent_run_id = str(payload.get("agent_run_id") or "") or self._agent_runs.get(agent, "")
        stream_id = str(payload.get("stream_id") or "")
        scope = EventScope(agent_run_id=agent_run_id) if agent_run_id else EventScope()
        return [
            self._emit(
                "text",
                {
                    "channel": "assistant",
                    "text": message,
                    "streamId": stream_id,
                },
                scope=scope,
            )
        ]

    def _on_agent_output_delta(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        delta = str(payload.get("delta") or "")
        if not delta:
            return []
        agent_run_id = str(payload.get("agent_run_id") or "") or self._agent_runs.get(agent, "")
        stream_id = str(payload.get("stream_id") or "")
        scope = EventScope(agent_run_id=agent_run_id) if agent_run_id else EventScope()
        return [
            self._emit(
                "text",
                {"channel": "assistant", "delta": delta, "streamId": stream_id},
                scope=scope,
            )
        ]

    def _on_assistant_delta(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        delta = str(payload.get("delta") or "")
        if not delta:
            return []
        agent_run_id = str(payload.get("agent_run_id") or "") or self._agent_runs.get(agent, "")
        scope = EventScope(agent_run_id=agent_run_id) if agent_run_id else EventScope()
        return [self._emit("text", {"channel": "assistant", "delta": delta}, scope=scope)]

    # -- tools -------------------------------------------------------------------

    def _on_tool_call_delta(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        agent_run_id = str(payload.get("agent_run_id") or "") or self._agent_runs.get(agent, "")
        out: list[LingxiMothershipEventV1] = []
        for call in payload.get("calls") or []:
            if not isinstance(call, dict):
                continue
            tool_call_id = str(call.get("id") or "")
            name = str(call.get("name") or "")
            if not tool_call_id or not name:
                continue
            scope = EventScope(agent_run_id=agent_run_id) if agent_run_id else EventScope()
            out.append(
                self._emit(
                    "tool",
                    {
                        "toolCallId": tool_call_id,
                        "toolKind": "tool",
                        "toolName": name,
                        "displayTitle": display_title(name) or name,
                        "status": "generating",
                        "safeParams": (
                            public_tool_params(name, call.get("args"))
                            if is_known_tool(name)
                            else {}
                        ),
                    },
                    scope=scope,
                )
            )
        return out

    def _on_tool_result(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        agent_run_id = str(payload.get("agent_run_id") or "") or self._agent_runs.get(agent, "")
        tool_call_id = str(payload.get("tool_call_id") or "")
        name = str(payload.get("name") or "")
        if not tool_call_id or not name:
            return []
        status_value = str(payload.get("status") or "")
        status = "error" if status_value in _TOOL_ERROR_STATUSES else "success"
        scope = EventScope(agent_run_id=agent_run_id) if agent_run_id else EventScope()
        safe_result = (
            public_tool_result(name, payload.get("content"), status_value)
            if is_known_tool(name)
            else {"ok": status == "success"}
        )
        return [
            self._emit(
                "tool",
                {
                    "toolCallId": tool_call_id,
                    "toolKind": "tool",
                    "toolName": name,
                    "displayTitle": display_title(name) or name,
                    "status": status,
                    "safeResult": safe_result,
                },
                scope=scope,
            )
        ]

    # -- resources ----------------------------------------------------------------

    def _on_artifact_ready(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        artifact = str(payload.get("artifact") or "")
        if not artifact:
            return []
        agent_run_id = str(payload.get("agent_run_id") or "") or self._agent_runs.get(agent, "")
        resource_id = f"artifact:{self._stream.chat_id}:{artifact}"
        return [
            self._emit(
                "resource",
                {
                    "resource": {
                        "id": resource_id,
                        "type": "file",
                        "title": artifact,
                        "path": str(payload.get("relative_path") or ""),
                        "sourceAgentRunId": agent_run_id,
                        "artifactKind": artifact,
                    },
                    "removed": False,
                },
                scope=EventScope(agent_run_id=agent_run_id) if agent_run_id else EventScope(),
            )
        ]

    # -- fallback -------------------------------------------------------------------

    def _generic(self, event: dict[str, Any], payload: dict[str, Any], agent: str) -> list[LingxiMothershipEventV1]:
        # Internal mechanics (node.*, model.*, delivery.*, plan.*, state.*,
        # goal.*) are deliberately not public V1 facts. The V0 stream keeps
        # them for today's UI; V1 publishes only canonical identities.
        return []

    # -- internals --------------------------------------------------------------------

    def _emit(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        scope: EventScope | None = None,
    ) -> LingxiMothershipEventV1:
        # The projector uses camelCase payload fields matching the V1 schema.
        envelope = self._encoder.encode(
            seq=self._seq,
            event_type=event_type,  # type: ignore[arg-type]
            payload=payload,
            stream=self._stream,
            scope=scope,
            trace=self._trace,
            ts=now_iso(),
        )
        self._seq += 1
        return envelope

    def renumber(self, events: list[dict[str, Any]], base_seq: int) -> list[dict[str, Any]]:
        """Rewrite placeholder seqs to the durable task sequence.

        Called by the repository when the append assigns final sequence
        numbers, keeping envelope ``seq`` equal to the row's ``sequence`` so
        ``Last-Event-ID`` reconnect works uniformly.
        """

        for index, event in enumerate(events):
            event["seq"] = base_seq + index
            stream = event.get("stream") or {}
            if not stream.get("executionId"):
                stream["executionId"] = self._stream.execution_id
                event["stream"] = stream
        return events


def project_event(
    event: dict[str, Any],
    *,
    chat_id: str,
    execution_id: str,
    turn_id: str = "",
) -> list[dict[str, Any]]:
    """One-shot projection convenience for tests and tooling."""

    projector = PublicProjector(chat_id=chat_id, execution_id=execution_id, turn_id=turn_id)
    return projector.consume(event)


__all__ = ["PublicProjector", "project_event", "validate_public_payload"]
