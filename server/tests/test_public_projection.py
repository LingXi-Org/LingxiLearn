"""Public projection tests: internal V0 events → Mothership Stream V1 (issue #18)."""

from __future__ import annotations

import json

from lingxilearn.runtime.public_projection import PublicProjector


def _projector() -> PublicProjector:
    return PublicProjector(
        chat_id="task_1", execution_id="exec_1", turn_id="turn_1", request_id="exec_1"
    )


def test_run_lifecycle_maps_to_run_and_complete() -> None:
    p = _projector()
    events = p.consume({"kind": "run.started", "agent": "coordinator", "payload": {}})
    assert [e["payload"]["status"] for e in events] == ["started"]

    events = p.consume({"kind": "run.completed", "agent": "coordinator", "payload": {}})
    statuses = [(e["type"], e["payload"]["status"]) for e in events]
    assert ("run", "completed") in statuses
    assert ("complete", "delivered") in statuses

    # Only one terminal pair, even if V0 emits several terminal kinds.
    events = p.consume({"kind": "task.completed", "agent": "coordinator", "payload": {}})
    assert events == []


def test_span_start_requires_real_identity() -> None:
    p = _projector()
    # Legacy provider-emitted start without dispatcher identity: no span, and
    # crucially no synthesized agent_run_id (issue #18 §3.2).
    events = p.consume({"kind": "agent.started", "agent": "answer_user", "payload": {}})
    assert events == []

    events = p.consume(
        {
            "kind": "agent.started",
            "agent": "answer_user",
            "payload": {"agent_run_id": "ar_1", "display_name": "知识点答疑"},
        }
    )
    assert len(events) == 1
    span = events[0]
    assert span["type"] == "span"
    assert span["payload"]["agentRunId"] == "ar_1"
    assert span["payload"]["displayName"] == "知识点答疑"
    assert span["scope"]["agentRunId"] == "ar_1"

    # Duplicate start for the same run is idempotent.
    again = p.consume(
        {
            "kind": "agent.started",
            "agent": "answer_user",
            "payload": {"agent_run_id": "ar_1", "display_name": "知识点答疑"},
        }
    )
    assert again == []


def test_span_end_binds_to_the_started_run() -> None:
    p = _projector()
    p.consume(
        {
            "kind": "agent.started",
            "agent": "answer_user",
            "payload": {"agent_run_id": "ar_1"},
        }
    )
    events = p.consume({"kind": "agent.completed", "agent": "answer_user", "payload": {}})
    assert len(events) == 1
    assert events[0]["payload"] == {
        "kind": "agent",
        "event": "end",
        "agentRunId": "ar_1",
        "status": "completed",
    }
    # An end without a start is dropped, not invented.
    assert p.consume({"kind": "agent.failed", "agent": "ghost", "payload": {}}) == []


def test_status_lines_become_scoped_narration() -> None:
    p = _projector()
    p.consume(
        {
            "kind": "agent.started",
            "agent": "visual_explainer",
            "payload": {"agent_run_id": "ar_v"},
        }
    )
    events = p.consume(
        {
            "kind": "agent.status",
            "agent": "visual_explainer",
            "payload": {"text": "正在生成交互式可视化…"},
        }
    )
    assert len(events) == 1
    assert events[0]["type"] == "text"
    assert events[0]["payload"]["channel"] == "narration"
    assert events[0]["scope"]["agentRunId"] == "ar_v"
    # Narration with no bound agent run stays unscoped, source=system.
    events = p.consume({"kind": "agent.status", "agent": "", "payload": {"text": "正在准备…"}})
    assert events[0]["payload"]["source"] == "system"
    assert events[0]["scope"]["agentRunId"] == ""


def test_agent_output_becomes_assistant_text() -> None:
    p = _projector()
    p.consume(
        {
            "kind": "agent.started",
            "agent": "answer_user",
            "payload": {"agent_run_id": "ar_p", "presentation_role": "primary"},
        }
    )
    events = p.consume(
        {
            "kind": "agent.output",
            "agent": "answer_user",
            "payload": {"message": "答案正文", "stream_id": "s1"},
        }
    )
    assert events[0]["payload"]["channel"] == "assistant"
    assert events[0]["payload"]["text"] == "答案正文"
    assert events[0]["payload"]["streamId"] == "s1"


def test_only_primary_agent_writes_top_level_chat_content() -> None:
    """Supporting/background output narrates in its own AgentGroup (§6.2)."""

    p = _projector()
    p.consume(
        {
            "kind": "agent.started",
            "agent": "answer_user",
            "payload": {"agent_run_id": "ar_primary", "presentation_role": "primary"},
        }
    )
    p.consume(
        {
            "kind": "agent.started",
            "agent": "visual_explainer",
            "payload": {"agent_run_id": "ar_support", "presentation_role": "supporting"},
        }
    )
    primary = p.consume(
        {
            "kind": "agent.output",
            "agent": "answer_user",
            "payload": {"message": "叠加态是…", "stream_id": "s1"},
        }
    )
    assert primary[0]["payload"]["channel"] == "assistant"
    assert primary[0]["scope"]["agentRunId"] == "ar_primary"

    supporting = p.consume(
        {
            "kind": "agent.output",
            "agent": "visual_explainer",
            "payload": {"message": "可视化已生成。", "stream_id": "s2"},
        }
    )
    assert supporting[0]["payload"]["channel"] == "narration"
    assert supporting[0]["scope"]["agentRunId"] == "ar_support"
    assert supporting[0]["payload"]["text"] == "可视化已生成。"

    # A supporting run's partial deltas never reach a top-level buffer.
    assert (
        p.consume(
            {
                "kind": "agent.output.delta",
                "agent": "visual_explainer",
                "payload": {"delta": "半句", "stream_id": "s2"},
            }
        )
        == []
    )
    deltas = p.consume(
        {
            "kind": "agent.output.delta",
            "agent": "answer_user",
            "payload": {"delta": "叠加", "stream_id": "s1"},
        }
    )
    assert deltas[0]["payload"]["channel"] == "assistant"
    assert deltas[0]["payload"]["delta"] == "叠加"


def test_raw_assistant_delta_never_reaches_the_learner() -> None:
    """The provider's raw model stream is not a public lane (§5.4).

    Structured providers parse, validate and safety-check that stream before
    publishing ``agent.output*``; publishing it directly would send partial
    JSON and unvalidated content to the browser.
    """

    p = _projector()
    p.consume(
        {
            "kind": "agent.started",
            "agent": "answer_user",
            "payload": {"agent_run_id": "ar_primary", "presentation_role": "primary"},
        }
    )
    raw = p.consume(
        {
            "kind": "assistant.delta",
            "agent": "answer_user",
            "payload": {"delta": '{"answer": "泄题：正确选项是 B", "confid'},
        }
    )
    assert raw == []

    published = p.consume(
        {
            "kind": "agent.output",
            "agent": "answer_user",
            "payload": {"message": "先想想两个态叠加意味着什么。", "stream_id": "s1"},
        }
    )
    assert [e["payload"]["channel"] for e in published] == ["assistant"]
    assert published[0]["payload"]["text"] == "先想想两个态叠加意味着什么。"


def test_system_acknowledgement_stays_top_level_without_an_agent() -> None:
    p = _projector()
    events = p.consume(
        {
            "kind": "agent.output",
            "agent": "learning_companion",
            "payload": {"message": "我先陪你开始…", "stream_id": "t:opening-companion"},
        }
    )
    assert events[0]["payload"]["channel"] == "assistant"
    assert events[0]["payload"]["source"] == "system"
    assert events[0]["scope"]["agentRunId"] == ""


def test_cancelled_skill_run_keeps_cancelled_semantics() -> None:
    p = _projector()
    p.consume(
        {
            "kind": "skill.started",
            "agent": "answer_user",
            "payload": {
                "skill_run_id": "sr_1",
                "agent_run_id": "ar_1",
                "skill_id": "knowledge-qa",
                "display_name": "知识点答疑",
            },
        }
    )
    cancelled = p.consume(
        {
            "kind": "skill.failed",
            "agent": "answer_user",
            "payload": {"skill_run_id": "sr_1", "agent_run_id": "ar_1", "status": "cancelled"},
        }
    )
    assert cancelled[0]["payload"]["status"] == "cancelled"
    failed = p.consume(
        {
            "kind": "skill.failed",
            "agent": "answer_user",
            "payload": {"skill_run_id": "sr_1", "agent_run_id": "ar_1", "status": "failed"},
        }
    )
    assert failed[0]["payload"]["status"] == "error"


def test_tool_events_are_sanitized() -> None:
    p = _projector()
    call = p.consume(
        {
            "kind": "tool.call.delta",
            "agent": "lecture_deck",
            "payload": {
                "calls": [
                    {
                        "id": "call_1",
                        "name": "stage_artifact_file",
                        "args": {"path": "dist/index.html", "content": "<html>...big..."},
                    }
                ]
            },
        }
    )
    assert len(call) == 1
    assert call[0]["payload"]["toolName"] == "stage_artifact_file"
    assert call[0]["payload"]["displayTitle"] == "写入学习产物"
    assert call[0]["payload"]["safeParams"] == {"path": "dist/index.html", "bytes": 15}
    assert "content" not in json.dumps(call[0]["payload"]["safeParams"])

    result = p.consume(
        {
            "kind": "tool.result",
            "agent": "lecture_deck",
            "payload": {
                "tool_call_id": "call_1",
                "name": "stage_artifact_file",
                "content": "staged ok",
                "status": "success",
            },
        }
    )
    assert result[0]["payload"]["safeResult"] == {"ok": True, "bytes": 9}


def test_unknown_tool_gets_status_only() -> None:
    p = _projector()
    call = p.consume(
        {
            "kind": "tool.call.delta",
            "agent": "x",
            "payload": {"calls": [{"id": "c9", "name": "custom_tool", "args": {"secret": 1}}]},
        }
    )
    assert call[0]["payload"]["safeParams"] == {}
    assert call[0]["payload"]["status"] == "generating"


def test_skill_lifecycle_maps_to_skill_tool_calls() -> None:
    p = _projector()
    start = p.consume(
        {
            "kind": "skill.started",
            "agent": "adaptive_pedagogy",
            "payload": {
                "agent_run_id": "ar_2",
                "skill_run_id": "sr_2",
                "skill_id": "adaptive-pedagogy",
                "display_name": "自适应教学",
                "version": "1.1.0",
            },
        }
    )
    assert start[0]["payload"]["toolKind"] == "skill"
    assert start[0]["payload"]["toolCallId"] == "sr_2"
    assert start[0]["payload"]["displayTitle"] == "自适应教学"
    assert start[0]["payload"]["safeParams"] == {
        "skillId": "adaptive-pedagogy",
        "version": "1.1.0",
    }
    assert start[0]["scope"]["skillRunId"] == "sr_2"

    end = p.consume(
        {
            "kind": "skill.completed",
            "agent": "adaptive_pedagogy",
            "payload": {"agent_run_id": "ar_2", "skill_run_id": "sr_2"},
        }
    )
    assert end[0]["payload"]["status"] == "success"


def test_artifact_ready_maps_to_resource_upsert() -> None:
    p = _projector()
    events = p.consume(
        {
            "kind": "artifact.ready",
            "agent": "visual_explainer",
            "payload": {"artifact": "visual", "relative_path": "t/visual/dist/index.html"},
        }
    )
    assert len(events) == 1
    resource = events[0]["payload"]["resource"]
    assert resource["type"] == "file"
    assert resource["artifactKind"] == "visual"
    assert resource["path"] == "t/visual/dist/index.html"
    assert events[0]["type"] == "resource"


def test_internal_mechanics_are_not_public() -> None:
    p = _projector()
    for kind in ("node.started", "node.completed", "model.started", "plan.created", "state.updated"):
        assert p.consume({"kind": kind, "agent": "orchestrator", "payload": {}}) == []


def test_renumber_assigns_durable_sequence() -> None:
    p = _projector()
    events = p.consume({"kind": "run.started", "agent": "coordinator", "payload": {}})
    renumbered = p.renumber(events, base_seq=41)
    assert renumbered[0]["seq"] == 41
    assert renumbered[0]["stream"]["executionId"] == "exec_1"


def test_typed_interaction_pause_exposes_identity_only() -> None:
    p = _projector()
    events = p.consume(
        {
            "kind": "run.paused",
            "agent": "coordinator",
            "payload": {
                "interrupts": [{"kind": "interaction", "interaction_id": "it_9"}],
                "graph_state": {"plan": {"reasoning": "hidden"}},
            },
        }
    )
    assert events[0]["payload"] == {
        "status": "checkpoint_pause",
        "executionId": "exec_1",
        "interactionId": "it_9",
    }
