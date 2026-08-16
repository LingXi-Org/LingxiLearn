"""Durable, exactly-once interaction continuations (issue #18 §10.4).

Answering a blocking interaction must be a single atomic step: the structured
answer, the pending→resolved transition and the continuation command commit
together.  Nothing may leave a thread resolved-but-never-resumed, and two
concurrent answers may not both resume the same checkpoint.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio

from lingxilearn.config import Settings
from lingxilearn.service import Service

ANSWERS = [{"questionId": "q1", "selectedOptionIds": ["o2"], "text": None}]


@pytest_asyncio.fixture
async def paused_thread(tmp_path: Path):
    """A thread paused on one blocking interaction, with resumes captured."""

    suffix = uuid4().hex
    settings = Settings(
        _env_file="",
        database_url=f"sqlite+aiosqlite:///./var/interaction-continuation-{suffix}.sqlite3",
        agent_task_dir=tmp_path,
    )
    service = Service(settings)
    await service.db.create_all()
    resumes: list[dict[str, Any]] = []

    def capture_spawn(coro: Any) -> None:
        # The spawn is the fast path only; the ledger is what this suite tests.
        coro.close()

    async def capture_drive(
        task_id: str, learner_id: str, prompt: str, **kwargs: Any
    ) -> None:  # pragma: no cover - replaced per test
        resumes.append(dict(kwargs.get("resume") or {}))

    service._spawn = capture_spawn  # type: ignore[method-assign]
    service._drive_agent_task = capture_drive  # type: ignore[method-assign]

    learner_id = f"learner-{suffix}"
    task_id = f"task-{suffix}"
    await service.repo.ensure_learner(learner_id)
    await service.repo.create_agent_task(
        id=task_id,
        learner_id=learner_id,
        prompt="帮我准备一下量子力学",
        graph_version="test@1",
        status="awaiting_user",
    )
    command = await service.repo.append_command(
        task_id=task_id,
        kind="message",
        payload={"message": "帮我准备一下量子力学"},
        idempotency_key=f"msg:{suffix}",
    )
    turn_id = str(command["turn_id"])
    interaction_id = f"it_{suffix}"
    await service.repo.create_interaction(
        interaction_id=interaction_id,
        task_id=task_id,
        turn_id=turn_id,
        execution_id=f"exec-{suffix}",
        request_payload={"prompt": "你想先学哪个方向？"},
        blocking=True,
        reason_code="goal_ambiguous",
    )
    try:
        yield service, task_id, learner_id, interaction_id, turn_id
    finally:
        await service.db.dispose()


async def test_answer_commits_a_durable_continuation_command(paused_thread) -> None:
    service, task_id, learner_id, interaction_id, turn_id = paused_thread

    result = await service.answer_agent_interaction(
        task_id,
        interaction_id,
        answers=ANSWERS,
        idempotency_key="ans-1",
        learner_id=learner_id,
    )
    assert result["status"] == "accepted"

    interaction = await service.repo.get_interaction(interaction_id, task_id=task_id)
    assert interaction is not None and interaction["status"] == "resolved"

    pending = [
        command
        for command in await service.repo.pending_commands(task_id)
        if command["kind"] == "interaction_answer"
    ]
    assert len(pending) == 1
    assert pending[0]["payload"]["interaction_id"] == interaction_id
    assert pending[0]["payload"]["answers"] == ANSWERS
    # The continuation stays inside the turn that paused; it never opens one.
    assert pending[0]["turn_id"] == turn_id
    latest = await service.repo.latest_turn(task_id)
    assert latest is not None and latest["id"] == turn_id


async def test_crash_between_commit_and_resume_is_recovered(paused_thread) -> None:
    """A process death after the commit must not strand the thread."""

    service, task_id, learner_id, interaction_id, _turn = paused_thread
    await service.answer_agent_interaction(
        task_id,
        interaction_id,
        answers=ANSWERS,
        idempotency_key="ans-1",
        learner_id=learner_id,
    )

    # Simulate the restart: nothing in memory, only the durable ledger.
    replayed: list[tuple[str, dict[str, Any]]] = []
    started: list[asyncio.Task[Any]] = []

    def spawn(coro: Any) -> None:
        started.append(asyncio.ensure_future(coro))

    async def drive(task: str, learner: str, prompt: str, **kwargs: Any) -> None:
        replayed.append((task, dict(kwargs.get("resume") or {})))

    service._spawn = spawn  # type: ignore[method-assign]
    service._drive_agent_task = drive  # type: ignore[method-assign]

    recovered = await service._recover_interaction_continuations()
    await asyncio.gather(*started)
    assert recovered == 1
    assert replayed == [
        (
            task_id,
            {
                "kind": "interaction_answer",
                "interaction_id": interaction_id,
                "answers": ANSWERS,
            },
        )
    ]

    # Once the turn consumes the command, recovery stops replaying it.
    for command in await service.repo.pending_commands(task_id):
        await service.repo.consume_command(str(command["id"]))
    replayed.clear()
    started.clear()
    assert await service._recover_interaction_continuations() == 0
    await asyncio.gather(*started)
    assert replayed == []


async def test_answer_during_a_running_turn_resumes_without_a_restart(paused_thread) -> None:
    """The fast-path resume cannot claim a running thread; the drain must.

    A learner can answer through SSE before the current execution has fully
    settled.  The continuation is durable at that moment, but
    ``claim_agent_task`` refuses a running thread, so the first resume attempt
    does nothing.  The finishing execution has to pick it up — waiting for a
    process restart would strand the thread.
    """

    service, task_id, learner_id, interaction_id, _turn = paused_thread
    resumes: list[dict[str, Any]] = []
    started: list[asyncio.Task[Any]] = []

    def spawn(coro: Any) -> None:
        started.append(asyncio.ensure_future(coro))

    async def drive(task: str, learner: str, prompt: str, **kwargs: Any) -> None:
        # The real claim refuses a running thread; model exactly that.
        record = await service.repo.get_agent_task_for_learner(task, learner)
        if record is not None and record.status == "running":
            return
        resumes.append(dict(kwargs.get("resume") or {}))

    service._spawn = spawn  # type: ignore[method-assign]
    service._drive_agent_task = drive  # type: ignore[method-assign]

    # The previous execution is still running when the answer arrives.
    await service.repo.set_agent_task_status(task_id, "running", thread_status="running")
    result = await service.answer_agent_interaction(
        task_id,
        interaction_id,
        answers=ANSWERS,
        idempotency_key="ans-race",
        learner_id=learner_id,
    )
    await asyncio.gather(*started)
    assert result["status"] == "accepted"
    assert resumes == [], "a running thread cannot be claimed by the fast path"
    pending = [
        command
        for command in await service.repo.pending_commands(task_id)
        if command["kind"] == "interaction_answer"
    ]
    assert len(pending) == 1, "the continuation stays durable"

    # The execution finishes and releases the thread.
    started.clear()
    await service.repo.set_agent_task_status(task_id, "completed", thread_status="open")
    drained = await service._drain_interaction_continuations(task_id, learner_id)
    await asyncio.gather(*started)

    assert drained == 1
    assert resumes == [
        {
            "kind": "interaction_answer",
            "interaction_id": interaction_id,
            "answers": ANSWERS,
        }
    ]
    remaining = [
        command
        for command in await service.repo.pending_commands(task_id)
        if command["kind"] == "interaction_answer"
    ]
    assert remaining == [], "a drained continuation is consumed exactly once"

    # A second drain is a no-op rather than a replay.
    assert await service._drain_interaction_continuations(task_id, learner_id) == 0
    assert len(resumes) == 1


async def test_drain_defers_while_another_turn_owns_the_thread(paused_thread) -> None:
    service, task_id, learner_id, interaction_id, _turn = paused_thread
    resumes: list[dict[str, Any]] = []

    def spawn(coro: Any) -> None:
        coro.close()

    async def drive(task: str, learner: str, prompt: str, **kwargs: Any) -> None:
        resumes.append(dict(kwargs.get("resume") or {}))

    service._spawn = spawn  # type: ignore[method-assign]
    service._drive_agent_task = drive  # type: ignore[method-assign]

    await service.answer_agent_interaction(
        task_id,
        interaction_id,
        answers=ANSWERS,
        idempotency_key="ans-defer",
        learner_id=learner_id,
    )
    await service.repo.set_agent_task_status(task_id, "running", thread_status="running")

    assert await service._drain_interaction_continuations(task_id, learner_id) == 0
    assert resumes == [], "the live turn's own tail drains it"
    pending = [
        command
        for command in await service.repo.pending_commands(task_id)
        if command["kind"] == "interaction_answer"
    ]
    assert len(pending) == 1


async def test_concurrent_answers_produce_exactly_one_continuation(paused_thread) -> None:
    service, task_id, learner_id, interaction_id, _turn = paused_thread

    async def answer(key: str, option: str) -> Any:
        try:
            return await service.answer_agent_interaction(
                task_id,
                interaction_id,
                answers=[{"questionId": "q1", "selectedOptionIds": [option], "text": None}],
                idempotency_key=key,
                learner_id=learner_id,
            )
        except Exception as exc:  # noqa: BLE001 - the loser's outcome is the assertion
            return exc

    first, second = await asyncio.gather(answer("ans-a", "o1"), answer("ans-b", "o2"))
    outcomes = sorted(
        [item["status"] if isinstance(item, dict) else "error" for item in (first, second)]
    )
    assert outcomes == ["accepted", "already_resolved"]

    commands = [
        command
        for command in await service.repo.pending_commands(task_id)
        if command["kind"] == "interaction_answer"
    ]
    assert len(commands) == 1, "a blocking interaction resumes its checkpoint exactly once"


async def test_same_key_is_idempotent_and_a_changed_payload_conflicts(paused_thread) -> None:
    service, task_id, learner_id, interaction_id, _turn = paused_thread

    first = await service.answer_agent_interaction(
        task_id,
        interaction_id,
        answers=ANSWERS,
        idempotency_key="ans-1",
        learner_id=learner_id,
    )
    replay = await service.answer_agent_interaction(
        task_id,
        interaction_id,
        answers=ANSWERS,
        idempotency_key="ans-1",
        learner_id=learner_id,
    )
    assert first["status"] == replay["status"] == "accepted"
    commands = [
        command
        for command in await service.repo.pending_commands(task_id)
        if command["kind"] == "interaction_answer"
    ]
    assert len(commands) == 1

    with pytest.raises(ValueError, match="idempotency_key_reused"):
        await service.answer_agent_interaction(
            task_id,
            interaction_id,
            answers=[{"questionId": "q1", "selectedOptionIds": ["o1"], "text": None}],
            idempotency_key="ans-1",
            learner_id=learner_id,
        )
