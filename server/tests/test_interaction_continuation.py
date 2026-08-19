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

from lingxilearn.application import ApplicationServices
from lingxilearn.config import Settings

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
    services = ApplicationServices(settings)
    await services.db.create_all()
    resumes: list[dict[str, Any]] = []

    def capture_spawn(coro: Any) -> None:
        # The spawn is the fast path only; the ledger is what this suite tests.
        coro.close()

    async def capture_drive(
        task_id: str, learner_id: str, prompt: str, **kwargs: Any
    ) -> None:  # pragma: no cover - replaced per test
        resumes.append(dict(kwargs.get("resume") or {}))

    services.tasks.spawn = capture_spawn  # type: ignore[method-assign]
    services.runtime._drive_agent_task = capture_drive  # type: ignore[method-assign]

    learner_id = f"learner-{suffix}"
    task_id = f"task-{suffix}"
    await services.learner_repository.ensure_learner(learner_id)
    await services.agent_task_repository.create_agent_task(
        id=task_id,
        learner_id=learner_id,
        prompt="帮我准备一下量子力学",
        graph_version="test@1",
        status="awaiting_user",
    )
    command = await services.work_ledger.append_command(
        task_id=task_id,
        kind="message",
        payload={"message": "帮我准备一下量子力学"},
        idempotency_key=f"msg:{suffix}",
    )
    turn_id = str(command["turn_id"])
    interaction_id = f"it_{suffix}"
    await services.runtime_repository.create_interaction(
        interaction_id=interaction_id,
        task_id=task_id,
        turn_id=turn_id,
        execution_id=f"exec-{suffix}",
        request_payload={"prompt": "你想先学哪个方向？"},
        blocking=True,
        reason_code="goal_ambiguous",
    )
    try:
        yield services, task_id, learner_id, interaction_id, turn_id
    finally:
        await services.db.dispose()


async def test_answer_commits_a_durable_continuation_command(paused_thread) -> None:
    services, task_id, learner_id, interaction_id, turn_id = paused_thread

    result = await services.agent_tasks.answer_agent_interaction(
        task_id,
        interaction_id,
        answers=ANSWERS,
        idempotency_key="ans-1",
        learner_id=learner_id,
    )
    assert result["status"] == "accepted"

    interaction = await services.runtime_repository.get_interaction(interaction_id, task_id=task_id)
    assert interaction is not None and interaction["status"] == "resolved"

    pending = [
        command
        for command in await services.work_ledger.pending_commands(task_id)
        if command["kind"] == "interaction_answer"
    ]
    assert len(pending) == 1
    assert pending[0]["payload"]["interaction_id"] == interaction_id
    assert pending[0]["payload"]["answers"] == ANSWERS
    # The continuation stays inside the turn that paused; it never opens one.
    assert pending[0]["turn_id"] == turn_id
    latest = await services.work_ledger.latest_turn(task_id)
    assert latest is not None and latest["id"] == turn_id


async def test_crash_between_commit_and_resume_is_recovered(paused_thread) -> None:
    """A process death after the commit must not strand the thread."""

    services, task_id, learner_id, interaction_id, _turn = paused_thread
    await services.agent_tasks.answer_agent_interaction(
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

    async def drive(task: str, learner: str, prompt: str, **kwargs: Any) -> bool:
        replayed.append((task, dict(kwargs.get("resume") or {})))
        return True

    services.tasks.spawn = spawn  # type: ignore[method-assign]
    services.runtime._drive_agent_task = drive  # type: ignore[method-assign]

    recovered = await services.runtime.recover_interaction_continuations()
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
    for command in await services.work_ledger.pending_commands(task_id):
        await services.work_ledger.consume_command(str(command["id"]))
    replayed.clear()
    started.clear()
    assert await services.runtime.recover_interaction_continuations() == 0
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

    services, task_id, learner_id, interaction_id, _turn = paused_thread
    resumes: list[dict[str, Any]] = []
    started: list[asyncio.Task[Any]] = []

    def spawn(coro: Any) -> None:
        started.append(asyncio.ensure_future(coro))

    async def drive(task: str, learner: str, prompt: str, **kwargs: Any) -> bool:
        # The real claim refuses a running thread; model exactly that, and
        # report ownership the way _run_agent_task now does.
        record = await services.agent_task_repository.get_agent_task_for_learner(task, learner)
        if record is not None and record.status == "running":
            return False
        resumes.append(dict(kwargs.get("resume") or {}))
        return True

    services.tasks.spawn = spawn  # type: ignore[method-assign]
    services.runtime._drive_agent_task = drive  # type: ignore[method-assign]

    # The previous execution is still running when the answer arrives.
    await services.agent_task_repository.set_agent_task_status(task_id, "running", thread_status="running")
    result = await services.agent_tasks.answer_agent_interaction(
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
        for command in await services.work_ledger.pending_commands(task_id)
        if command["kind"] == "interaction_answer"
    ]
    assert len(pending) == 1, "the continuation stays durable"

    # The execution finishes and releases the thread.
    started.clear()
    await services.agent_task_repository.set_agent_task_status(task_id, "completed", thread_status="open")
    drained = await services.runtime._drain_interaction_continuations(task_id, learner_id)
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
        for command in await services.work_ledger.pending_commands(task_id)
        if command["kind"] == "interaction_answer"
    ]
    assert remaining == [], "a drained continuation is consumed exactly once"

    # A second drain is a no-op rather than a replay.
    assert await services.runtime._drain_interaction_continuations(task_id, learner_id) == 0
    assert len(resumes) == 1


async def test_drain_defers_while_another_turn_owns_the_thread(paused_thread) -> None:
    services, task_id, learner_id, interaction_id, _turn = paused_thread
    resumes: list[dict[str, Any]] = []

    def spawn(coro: Any) -> None:
        coro.close()

    async def drive(task: str, learner: str, prompt: str, **kwargs: Any) -> bool:
        resumes.append(dict(kwargs.get("resume") or {}))
        return True

    services.tasks.spawn = spawn  # type: ignore[method-assign]
    services.runtime._drive_agent_task = drive  # type: ignore[method-assign]

    await services.agent_tasks.answer_agent_interaction(
        task_id,
        interaction_id,
        answers=ANSWERS,
        idempotency_key="ans-defer",
        learner_id=learner_id,
    )
    await services.agent_task_repository.set_agent_task_status(task_id, "running", thread_status="running")

    assert await services.runtime._drain_interaction_continuations(task_id, learner_id) == 0
    assert resumes == [], "the live turn's own tail drains it"
    pending = [
        command
        for command in await services.work_ledger.pending_commands(task_id)
        if command["kind"] == "interaction_answer"
    ]
    assert len(pending) == 1


async def test_a_losing_worker_never_consumes_the_continuation(paused_thread) -> None:
    """Only the worker that won the durable claim may close the ledger entry.

    The answer's fast path does not take the process-local drain lock, and
    another replica has a different lock entirely, so two workers can both hold
    the same pending continuation.  If the loser consumed it, a crash on the
    winning side would lose the answer with nothing left for startup recovery
    to replay: ownership of the run, not arrival, decides who may consume.
    """

    services, task_id, learner_id, interaction_id, _turn = paused_thread
    owned = False
    attempts: list[dict[str, Any]] = []

    def spawn(coro: Any) -> None:
        coro.close()

    async def drive(task: str, learner: str, prompt: str, **kwargs: Any) -> bool:
        # False is exactly what _run_agent_task returns when another worker
        # won claim_agent_task: nothing was executed here.
        attempts.append(dict(kwargs.get("resume") or {}))
        return owned

    services.tasks.spawn = spawn  # type: ignore[method-assign]
    services.runtime._drive_agent_task = drive  # type: ignore[method-assign]

    await services.agent_tasks.answer_agent_interaction(
        task_id,
        interaction_id,
        answers=ANSWERS,
        idempotency_key="ans-own",
        learner_id=learner_id,
    )

    assert await services.runtime._drain_interaction_continuations(task_id, learner_id) == 0
    assert len(attempts) == 1
    pending = [
        command
        for command in await services.work_ledger.pending_commands(task_id)
        if command["kind"] == "interaction_answer"
    ]
    assert len(pending) == 1, "a losing worker must not consume the winner's command"

    # The winner's own attempt closes it.
    owned = True
    assert await services.runtime._drain_interaction_continuations(task_id, learner_id) == 1
    remaining = [
        command
        for command in await services.work_ledger.pending_commands(task_id)
        if command["kind"] == "interaction_answer"
    ]
    assert remaining == [], "the owner closes the ledger entry when its run returns"


async def test_resolved_event_publishes_from_the_outbox_and_repairs(paused_thread) -> None:
    """The public resolved fact commits with the transition that produced it.

    A crash between the transaction and the publish leaves a durable outbox
    row; the retry (or a restart) must repair it, or a refreshed transcript
    would show a pending card for an interaction the database calls resolved.
    """

    services, task_id, learner_id, interaction_id, _turn = paused_thread

    def spawn(coro: Any) -> None:
        coro.close()

    async def drive(task: str, learner: str, prompt: str, **kwargs: Any) -> bool:
        return True

    services.tasks.spawn = spawn  # type: ignore[method-assign]
    services.runtime._drive_agent_task = drive  # type: ignore[method-assign]

    # Crash between claim_interaction_answer() and the publish.
    published = services.agent_events.publish_interaction_outbox

    async def crash(_task_id: str) -> int:
        raise RuntimeError("process died before publishing")

    services.agent_events.publish_interaction_outbox = crash  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        await services.agent_tasks.answer_agent_interaction(
            task_id,
            interaction_id,
            answers=ANSWERS,
            idempotency_key="ans-crash",
            learner_id=learner_id,
        )

    # Durable state says resolved; the replay log does not yet.
    interaction = await services.runtime_repository.get_interaction(interaction_id, task_id=task_id)
    assert interaction is not None and interaction["status"] == "resolved"
    events = await services.agent_task_repository.agent_events_after(task_id)
    assert not [event for event in events if event["kind"] == "interaction.resolved"]
    outbox = await services.work_ledger.pending_outbox(task_id=task_id)
    assert [row["event_key"] for row in outbox] == [f"interaction:{interaction_id}:resolved"]

    # The retry repairs it: same key, same payload, so the answer is the
    # original one and the missing public event is published.
    services.agent_events.publish_interaction_outbox = published  # type: ignore[method-assign]
    result = await services.agent_tasks.answer_agent_interaction(
        task_id,
        interaction_id,
        answers=ANSWERS,
        idempotency_key="ans-crash",
        learner_id=learner_id,
    )
    assert result["status"] == "accepted"

    events = await services.agent_task_repository.agent_events_after(task_id)
    resolved = [event for event in events if event["kind"] == "interaction.resolved"]
    assert len(resolved) == 1
    assert resolved[0]["payload"]["interaction_id"] == interaction_id
    assert resolved[0]["payload"]["answers"] == ANSWERS
    v1_resolved = [
        event
        for event in events
        if int(event.get("protocol_version") or 0) == 1
        and event["payload"].get("type") == "interaction"
    ]
    assert v1_resolved, "the V1 stream carries the resolved fact for the recap"
    assert await services.work_ledger.pending_outbox(task_id=task_id) == []

    # Publishing again is a no-op: the fact exists exactly once.
    assert await services.agent_events.publish_interaction_outbox(task_id) == 0
    events = await services.agent_task_repository.agent_events_after(task_id)
    assert len([event for event in events if event["kind"] == "interaction.resolved"]) == 1


async def test_ui_retry_with_a_new_key_repairs_and_resumes(paused_thread) -> None:
    """The real retry path: a new idempotency key, no restart.

    A failed publish fails the HTTP request, the card returns to active, and
    the learner clicks again — which mints a *new* key, so the repository
    answers ``already_resolved`` rather than ``duplicate``.  That branch must
    still publish the public fact and run the continuation, or the thread sits
    resolved-but-silent until someone restarts the process.
    """

    services, task_id, learner_id, interaction_id, _turn = paused_thread
    resumed: list[dict[str, Any]] = []
    started: list[asyncio.Task[Any]] = []

    def spawn(coro: Any) -> None:
        started.append(asyncio.ensure_future(coro))

    async def drive(task: str, learner: str, prompt: str, **kwargs: Any) -> bool:
        resumed.append(dict(kwargs.get("resume") or {}))
        return True

    services.tasks.spawn = spawn  # type: ignore[method-assign]
    services.runtime._drive_agent_task = drive  # type: ignore[method-assign]

    published = services.agent_events.publish_interaction_outbox

    async def crash(_task_id: str) -> int:
        raise RuntimeError("publish failed; the HTTP request fails too")

    services.agent_events.publish_interaction_outbox = crash  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        await services.agent_tasks.answer_agent_interaction(
            task_id,
            interaction_id,
            answers=ANSWERS,
            idempotency_key="lingxi-interaction-answer:first",
            learner_id=learner_id,
        )
    await asyncio.gather(*started)
    started.clear()
    assert resumed == [], "the failed attempt never reached the resume"

    # The learner clicks again: a different key, same durable interaction.
    services.agent_events.publish_interaction_outbox = published  # type: ignore[method-assign]
    result = await services.agent_tasks.answer_agent_interaction(
        task_id,
        interaction_id,
        answers=ANSWERS,
        idempotency_key="lingxi-interaction-answer:second",
        learner_id=learner_id,
    )
    await asyncio.gather(*started)
    assert result["status"] == "already_resolved"

    events = await services.agent_task_repository.agent_events_after(task_id)
    resolved = [event for event in events if event["kind"] == "interaction.resolved"]
    assert len(resolved) == 1, "the retry repaired the missing public fact exactly once"
    assert await services.work_ledger.pending_outbox(task_id=task_id) == []

    assert len(resumed) == 1, "the durable continuation ran, exactly once"
    assert resumed[0]["interaction_id"] == interaction_id
    remaining = [
        command
        for command in await services.work_ledger.pending_commands(task_id)
        if command["kind"] == "interaction_answer"
    ]
    assert remaining == []


async def test_two_publishers_write_the_resolved_fact_exactly_once(paused_thread) -> None:
    """Two replicas sharing one database may not both publish.

    The publisher used to read "does this event exist?" and then append —
    check-then-act, which two processes can both pass.  Claiming the outbox row
    and appending in one transaction is what makes it exactly-once.
    """

    services, task_id, learner_id, interaction_id, _turn = paused_thread

    def spawn(coro: Any) -> None:
        coro.close()

    async def drive(task: str, learner: str, prompt: str, **kwargs: Any) -> bool:
        return True

    services.tasks.spawn = spawn  # type: ignore[method-assign]
    services.runtime._drive_agent_task = drive  # type: ignore[method-assign]

    async def crash(_task_id: str) -> int:
        raise RuntimeError("publish deferred to the racing replicas")

    published = services.agent_events.publish_interaction_outbox
    services.agent_events.publish_interaction_outbox = crash  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        await services.agent_tasks.answer_agent_interaction(
            task_id,
            interaction_id,
            answers=ANSWERS,
            idempotency_key="ans-multi",
            learner_id=learner_id,
        )
    services.agent_events.publish_interaction_outbox = published  # type: ignore[method-assign]

    # A second process: its own Service/Repository over the same database, so
    # it shares no in-process lock with the first.
    replica = ApplicationServices(services.settings)
    replica.tasks.spawn = spawn  # type: ignore[method-assign]
    replica.runtime._drive_agent_task = drive  # type: ignore[method-assign]
    try:
        first, second = await asyncio.gather(
            services.agent_events.publish_interaction_outbox(task_id),
            replica.agent_events.publish_interaction_outbox(task_id),
        )
    finally:
        await replica.db.dispose()

    assert sorted((first, second)) == [0, 1], "exactly one replica published"

    events = await services.agent_task_repository.agent_events_after(task_id)
    v0_resolved = [event for event in events if event["kind"] == "interaction.resolved"]
    v1_resolved = [
        event
        for event in events
        if int(event.get("protocol_version") or 0) == 1
        and event["payload"].get("type") == "interaction"
    ]
    assert len(v0_resolved) == 1
    assert len(v1_resolved) == 1
    assert await services.work_ledger.pending_outbox(task_id=task_id) == []


async def test_startup_recovery_repairs_an_unpublished_resolution(paused_thread) -> None:
    services, task_id, learner_id, interaction_id, _turn = paused_thread
    started: list[asyncio.Task[Any]] = []

    def spawn(coro: Any) -> None:
        started.append(asyncio.ensure_future(coro))

    async def drive(task: str, learner: str, prompt: str, **kwargs: Any) -> bool:
        return True

    services.tasks.spawn = spawn  # type: ignore[method-assign]
    services.runtime._drive_agent_task = drive  # type: ignore[method-assign]

    async def crash(_task_id: str) -> int:
        raise RuntimeError("process died before publishing")

    published = services.agent_events.publish_interaction_outbox
    services.agent_events.publish_interaction_outbox = crash  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        await services.agent_tasks.answer_agent_interaction(
            task_id,
            interaction_id,
            answers=ANSWERS,
            idempotency_key="ans-restart",
            learner_id=learner_id,
        )
    services.agent_events.publish_interaction_outbox = published  # type: ignore[method-assign]

    assert await services.runtime.recover_interaction_continuations() == 1
    await asyncio.gather(*started)

    events = await services.agent_task_repository.agent_events_after(task_id)
    resolved = [event for event in events if event["kind"] == "interaction.resolved"]
    assert len(resolved) == 1, "restart repairs the missing public fact"
    assert await services.work_ledger.pending_outbox(task_id=task_id) == []


async def test_concurrent_answers_produce_exactly_one_continuation(paused_thread) -> None:
    services, task_id, learner_id, interaction_id, _turn = paused_thread

    async def answer(key: str, option: str) -> Any:
        try:
            return await services.agent_tasks.answer_agent_interaction(
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
        for command in await services.work_ledger.pending_commands(task_id)
        if command["kind"] == "interaction_answer"
    ]
    assert len(commands) == 1, "a blocking interaction resumes its checkpoint exactly once"


async def test_same_key_is_idempotent_and_a_changed_payload_conflicts(paused_thread) -> None:
    services, task_id, learner_id, interaction_id, _turn = paused_thread

    first = await services.agent_tasks.answer_agent_interaction(
        task_id,
        interaction_id,
        answers=ANSWERS,
        idempotency_key="ans-1",
        learner_id=learner_id,
    )
    replay = await services.agent_tasks.answer_agent_interaction(
        task_id,
        interaction_id,
        answers=ANSWERS,
        idempotency_key="ans-1",
        learner_id=learner_id,
    )
    assert first["status"] == replay["status"] == "accepted"
    commands = [
        command
        for command in await services.work_ledger.pending_commands(task_id)
        if command["kind"] == "interaction_answer"
    ]
    assert len(commands) == 1

    with pytest.raises(ValueError, match="idempotency_key_reused"):
        await services.agent_tasks.answer_agent_interaction(
            task_id,
            interaction_id,
            answers=[{"questionId": "q1", "selectedOptionIds": ["o1"], "text": None}],
            idempotency_key="ans-1",
            learner_id=learner_id,
        )
