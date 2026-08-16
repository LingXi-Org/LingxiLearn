"""Regenerate the shared Mothership Stream V1 fixtures.

Run from the repo root::

    python scripts/gen_mothership_v1_fixtures.py

The fixtures are the contract gate: the Python projector must produce them and
the TypeScript decoder must accept them (see ``server/tests/`` and
``web/lib/lingxi/generated/``).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "server"))

from lingxilearn.runtime.public_projection import PublicProjector  # noqa: E402

FIXTURE_DIR = REPO_ROOT / "contracts" / "fixtures" / "mothership-stream-v1"

CHAT = "task_fixture"
EXEC = "exec_fixture_1"
TURN = "turn_fixture_1"


def _projector() -> PublicProjector:
    return PublicProjector(chat_id=CHAT, execution_id=EXEC, turn_id=TURN, request_id=EXEC)


def _renumber(events: list[dict], base: int) -> list[dict]:
    for index, event in enumerate(events):
        event["seq"] = base + index
    return events


def single_primary_agent() -> list[dict]:
    p = _projector()
    events: list[dict] = []
    feed = [
        {"kind": "run.started", "agent": "coordinator", "payload": {}},
        {
            "kind": "agent.started",
            "agent": "answer_user",
            "payload": {
                "agent_run_id": "ar_answer1",
                "provider": "answer_user",
                "display_name": "知识点答疑",
                "execution_kind": "model",
                "capability": "dialog.answer",
                "presentation_role": "primary",
            },
        },
        {
            "kind": "skill.started",
            "agent": "answer_user",
            "payload": {
                "agent_run_id": "ar_answer1",
                "skill_run_id": "sr_qa1",
                "skill_id": "knowledge-qa",
                "display_name": "知识点答疑",
                "version": "1.0.0",
                "checksum": "sha256:abc",
            },
        },
        {
            "kind": "agent.status",
            "agent": "answer_user",
            "payload": {"agent_run_id": "ar_answer1", "text": "正在检索你提供的资料…"},
        },
        {
            "kind": "tool.call.delta",
            "agent": "answer_user",
            "payload": {
                "agent_run_id": "ar_answer1",
                "calls": [{"id": "call_web1", "name": "web_search", "args": {"query": "量子叠加"}}],
            },
        },
        {
            "kind": "tool.result",
            "agent": "answer_user",
            "payload": {
                "agent_run_id": "ar_answer1",
                "tool_call_id": "call_web1",
                "name": "web_search",
                "content": "<huge ranked blob>",
                "status": "success",
            },
        },
        {
            "kind": "skill.completed",
            "agent": "answer_user",
            "payload": {"agent_run_id": "ar_answer1", "skill_run_id": "sr_qa1", "status": "completed"},
        },
        {
            "kind": "agent.output",
            "agent": "answer_user",
            "payload": {
                "agent_run_id": "ar_answer1",
                "stream_id": "task_fixture:turn_fixture_1",
                "message": "量子叠加是指一个量子系统可以同时处于多个状态的线性组合。",
            },
        },
        {
            "kind": "agent.completed",
            "agent": "answer_user",
            "payload": {"agent_run_id": "ar_answer1", "status": "completed"},
        },
        {"kind": "run.completed", "agent": "coordinator", "payload": {}},
    ]
    for item in feed:
        events.extend(p.consume(item))
    return _renumber(events, 1)


def parallel_siblings() -> list[dict]:
    p = _projector()
    events: list[dict] = []
    feed = [
        {"kind": "run.started", "agent": "coordinator", "payload": {}},
        {
            "kind": "agent.started",
            "agent": "visual_explainer",
            "payload": {
                "agent_run_id": "ar_visual",
                "provider": "visual_explainer",
                "display_name": "可视化讲解",
                "execution_kind": "model",
                "capability": "content.visual",
                "presentation_role": "background",
            },
        },
        {
            "kind": "agent.started",
            "agent": "lecture_deck",
            "payload": {
                "agent_run_id": "ar_deck",
                "provider": "lecture_deck",
                "display_name": "交互式讲义",
                "execution_kind": "model",
                "capability": "content.deck",
                "presentation_role": "background",
            },
        },
        {
            "kind": "agent.status",
            "agent": "visual_explainer",
            "payload": {"agent_run_id": "ar_visual", "text": "正在生成交互式可视化…"},
        },
        {
            "kind": "agent.status",
            "agent": "lecture_deck",
            "payload": {"agent_run_id": "ar_deck", "text": "正在整理讲义结构…"},
        },
        {
            "kind": "artifact.ready",
            "agent": "visual_explainer",
            "payload": {
                "agent_run_id": "ar_visual",
                "artifact": "visual",
                "relative_path": "task_fixture/visual/dist/index.html",
            },
        },
        {
            "kind": "agent.completed",
            "agent": "visual_explainer",
            "payload": {"agent_run_id": "ar_visual", "status": "completed"},
        },
        {
            "kind": "agent.completed",
            "agent": "lecture_deck",
            "payload": {"agent_run_id": "ar_deck", "status": "completed"},
        },
        {"kind": "run.completed", "agent": "coordinator", "payload": {}},
    ]
    for item in feed:
        events.extend(p.consume(item))
    return _renumber(events, 1)


def blocking_question_pause() -> list[dict]:
    p = _projector()
    events: list[dict] = []
    feed = [
        {"kind": "run.started", "agent": "coordinator", "payload": {}},
        {
            "kind": "interrupt.raised",
            "agent": "coordinator",
            "payload": {
                # Legacy untyped interrupt: raw plan/messages must NOT survive
                # the projection (issue #18 §3.7).
                "interrupts": [
                    {
                        "kind": "user_message",
                        "task_id": CHAT,
                        "messages": ["内部消息"],
                        "plan": {"reasoning": "secret", "tasks": []},
                    }
                ]
            },
        },
    ]
    for item in feed:
        events.extend(p.consume(item))
    return _renumber(events, 1)


def run_failure() -> list[dict]:
    p = _projector()
    events: list[dict] = []
    feed = [
        {"kind": "run.started", "agent": "coordinator", "payload": {}},
        {
            "kind": "agent.started",
            "agent": "lecture_deck",
            "payload": {
                "agent_run_id": "ar_deck_fail",
                "provider": "lecture_deck",
                "display_name": "交互式讲义",
                "capability": "content.deck",
                "presentation_role": "supporting",
            },
        },
        {
            "kind": "agent.failed",
            "agent": "lecture_deck",
            "payload": {"agent_run_id": "ar_deck_fail", "status": "failed"},
        },
        {
            "kind": "run.failed",
            "agent": "coordinator",
            "payload": {"message": "运行失败：ProviderError: 模型不可用"},
        },
    ]
    for item in feed:
        events.extend(p.consume(item))
    return _renumber(events, 1)


def multi_turn_thread() -> list[dict]:
    p = _projector()
    events: list[dict] = []
    feed = [
        {"kind": "run.started", "agent": "coordinator", "payload": {}},
        {
            "kind": "agent.started",
            "agent": "answer_user",
            "payload": {
                "agent_run_id": "ar_t1",
                "provider": "answer_user",
                "display_name": "知识点答疑",
                "capability": "dialog.answer",
                "presentation_role": "primary",
            },
        },
        {
            "kind": "agent.output",
            "agent": "answer_user",
            "payload": {
                "agent_run_id": "ar_t1",
                "stream_id": "task_fixture:turn_fixture_1",
                "message": "叠加态是第一轮的答案。",
            },
        },
        {
            "kind": "agent.completed",
            "agent": "answer_user",
            "payload": {"agent_run_id": "ar_t1", "status": "completed"},
        },
        {"kind": "run.completed", "agent": "coordinator", "payload": {}},
    ]
    for item in feed:
        events.extend(p.consume(item))
    # Host-emitted turn events bracket the execution (issue #18 §5.2).
    turn1_started = p.turn_event(
        "started", turn_id="turn_fixture_1", turn_index=0, user_text="什么是量子叠加？"
    )
    turn1_delivered = p.turn_event("delivered", turn_id="turn_fixture_1", turn_index=0)
    turn2_started = p.turn_event(
        "started", turn_id="turn_fixture_2", turn_index=1, user_text="那测量之后为什么坍缩？"
    )
    turn2_delivered = p.turn_event("delivered", turn_id="turn_fixture_2", turn_index=1)
    events = [
        turn1_started,
        *events,
        turn1_delivered,
        turn2_started,
        turn2_delivered,
    ]
    return _renumber(events, 1)


SCENARIOS = {
    "single-primary-agent.json": single_primary_agent,
    "parallel-siblings.json": parallel_siblings,
    "blocking-question-pause.json": blocking_question_pause,
    "run-failure.json": run_failure,
    "multi-turn-thread.json": multi_turn_thread,
}


def main() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for name, builder in SCENARIOS.items():
        path = FIXTURE_DIR / name
        path.write_text(
            json.dumps(builder(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
