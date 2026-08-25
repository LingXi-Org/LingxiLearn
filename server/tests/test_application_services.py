"""Application service ownership and composition tests (issue #58).

The god object is gone when each focused service can be constructed with only
its own dependencies and exercised without the full application container.
"""

from __future__ import annotations

import ast
import asyncio
from collections import defaultdict
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio

from lingxilearn.application import (
    AgentEventService,
    AgentTaskService,
    ApplicationServices,
    ArtifactResourceService,
    ConversationService,
    LearnerStateService,
    LingxiGraphRuntimeAdapter,
    RuntimeInputPort,
)
from lingxilearn.application.container import ApplicationServices as ContainerServices
from lingxilearn.config import Settings

PACKAGE = Path(__file__).resolve().parents[1] / "lingxilearn" / "application"


def test_application_modules_have_no_import_cycle() -> None:
    """The application layer must stay a DAG: coordinators may compose, never cycle."""

    modules = sorted(PACKAGE.glob("*.py"))
    graph: dict[str, set[str]] = {}
    for module in modules:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        deps: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level:
                # Relative import inside the package.
                target = node.module or ""
                if target:
                    deps.add(target.rsplit(".", 1)[0])
        graph[module.stem] = deps

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str, trail: tuple[str, ...]) -> None:
        if node in visiting:
            raise AssertionError(f"import cycle: {' -> '.join((*trail, node))}")
        if node in visited or node not in graph:
            return
        visiting.add(node)
        for dep in graph[node]:
            visit(dep, (*trail, node))
        visiting.discard(node)
        visited.add(node)

    for node in graph:
        visit(node, ())


def test_no_single_service_exposes_cross_domain_surface() -> None:
    """Each cross-domain use-case has exactly one owning service."""

    services = (
        ConversationService,
        AgentTaskService,
        AgentEventService,
        ArtifactResourceService,
        LearnerStateService,
        LingxiGraphRuntimeAdapter,
    )
    expected_owners = {
        "create_session": ConversationService,
        "agent_message": AgentTaskService,
        "agent_execution_snapshot": AgentEventService,
        "upload_attachment": ArtifactResourceService,
        "project_agent_artifacts": ArtifactResourceService,
        "override_profile": LearnerStateService,
    }
    for name, owner in expected_owners.items():
        for cls in services:
            if cls is owner:
                assert callable(getattr(cls, name, None)), f"{owner.__name__} lost {name}"
            else:
                assert name not in vars(cls), f"{cls.__name__} unexpectedly owns {name}"
    # The composition root wires dependencies; it owns no business methods.
    assert not set(expected_owners) & set(vars(ApplicationServices))


def test_runtime_adapter_satisfies_the_input_port() -> None:
    adapter = LingxiGraphRuntimeAdapter.__new__(LingxiGraphRuntimeAdapter)
    assert isinstance(adapter, RuntimeInputPort)


@pytest.mark.asyncio
async def test_runtime_adapter_steers_the_canonical_execution() -> None:
    class Graph:
        calls: list[tuple[str, dict[str, Any]]] = []

        def steer(self, run_id: str, **kwargs: Any) -> Any:
            self.calls.append((run_id, kwargs))
            return type("Steering", (), {"id": "steer-1", "sequence": 1, "kind": "user_message"})()

    class Events:
        def __init__(self) -> None:
            self.rows: list[dict[str, Any]] = []

        async def append(self, _task_id: str, rows: list[dict[str, Any]]) -> None:
            self.rows.extend(rows)

        def notify(self, _task_id: str) -> None:
            pass

    class Ledger:
        delivered: list[tuple[str, str]] = []

        async def mark_command_delivered(self, command_id: str, execution_id: str) -> bool:
            self.delivered.append((command_id, execution_id))
            return True

    graph = Graph()
    events = Events()
    adapter = LingxiGraphRuntimeAdapter.__new__(LingxiGraphRuntimeAdapter)
    adapter._active_steering = {"task-1": (graph, "exec-1", "exec-1", "turn-1")}
    adapter._steering_deliveries = defaultdict(set)
    adapter._events = events
    adapter._work_ledger = Ledger()

    await adapter.submit_running_input(
        "task-1",
        "learner-1",
        {
            "message": "先讲直觉",
            "command_id": "cmd-1",
            "turn_id": "turn-1",
            "idempotency_key": "message-1",
        },
    )

    assert graph.calls[0][0] == "exec-1"
    assert graph.calls[0][1]["kind"] == "user_message"
    assert graph.calls[0][1]["idempotency_key"] == "message-1"
    assert adapter._work_ledger.delivered == [("cmd-1", "exec-1")]
    assert events.rows[0]["kind"] == "steer.accepted"


def test_legacy_interjection_queue_is_removed() -> None:
    package = PACKAGE.parent
    production = "\n".join(
        path.read_text(encoding="utf-8")
        for path in package.rglob("*.py")
        if "migrations" not in path.parts
    )
    assert "push_interjection" not in production
    assert "drain_interjections" not in production
    assert "SessionState.interjections" not in production


class _StubRuntimePort:
    """Captures turn submissions without running a graph."""

    def __init__(self) -> None:
        self.model_configured = True
        self.started: list[tuple[str, str, str]] = []
        self.resumed: list[tuple[str, str, dict[str, Any]]] = []
        self.enqueued: list[tuple[str, str, dict[str, Any]]] = []
        self.running_inputs: list[tuple[str, str, dict[str, Any]]] = []

    def start_turn(self, task_id: str, learner_id: str, prompt: str, **kwargs: Any) -> None:
        self.started.append((task_id, learner_id, prompt))

    def resume_turn(
        self, task_id: str, learner_id: str, resume: dict[str, Any], **kwargs: Any
    ) -> None:
        self.resumed.append((task_id, learner_id, resume))

    def enqueue_conversation_input(
        self, task_id: str, learner_id: str, item: dict[str, Any]
    ) -> None:
        self.enqueued.append((task_id, learner_id, item))

    async def submit_running_input(
        self, task_id: str, learner_id: str, item: dict[str, Any]
    ) -> None:
        self.running_inputs.append((task_id, learner_id, item))

    def schedule_interaction_drain(self, task_id: str, learner_id: str) -> None:
        raise AssertionError("not needed by these tests")

    async def cancel_run(self, task_id: str) -> None:
        return None

    async def recover_pending(self) -> None:
        return None


@pytest_asyncio.fixture
async def container(tmp_path: Path):
    suffix = uuid4().hex
    settings = Settings(
        _env_file="",
        database_url=f"sqlite+aiosqlite:///./var/app-services-{suffix}.sqlite3",
        agent_task_dir=tmp_path / "tasks",
        var_dir=tmp_path / "var",
    )
    services = ApplicationServices(settings)
    await services.db.create_all()
    try:
        yield services
    finally:
        await services.db.dispose()


@pytest.mark.asyncio
async def test_agent_task_service_runs_through_the_runtime_port(container) -> None:
    """Task creation submits its turn through the port, not a concrete adapter."""

    services = container
    port = _StubRuntimePort()
    focused = AgentTaskService(
        agent_task_repository=services.agent_task_repository,
        work_ledger=services.work_ledger,
        runtime_repository=services.runtime_repository,
        runtime_state=services.runtime_state,
        learner_repository=services.learner_repository,
        db=services.db,
        artifact_service=services.artifacts,
        event_service=services.agent_events,
        runtime=port,
        board_locks=defaultdict(asyncio.Lock),
    )

    learner_id = f"learner-{uuid4().hex}"
    created = await focused.create_agent_task(
        task_id=f"task-{uuid4().hex}",
        learner_id=learner_id,
        prompt="解释 TCP 拥塞控制",
    )

    assert created["status"] == "queued"
    assert port.started and port.started[0][0] == created["id"]


@pytest.mark.asyncio
async def test_running_message_is_submitted_once_without_queue_replay(container) -> None:
    services = container
    port = _StubRuntimePort()
    focused = AgentTaskService(
        agent_task_repository=services.agent_task_repository,
        work_ledger=services.work_ledger,
        runtime_repository=services.runtime_repository,
        runtime_state=services.runtime_state,
        learner_repository=services.learner_repository,
        db=services.db,
        artifact_service=services.artifacts,
        event_service=services.agent_events,
        runtime=port,
        board_locks=defaultdict(asyncio.Lock),
    )
    learner_id = f"learner-{uuid4().hex}"
    task_id = f"task-{uuid4().hex}"
    await services.learner_repository.ensure_learner(learner_id)
    await services.agent_task_repository.create_agent_task(
        id=task_id,
        learner_id=learner_id,
        prompt="解释拥塞窗口",
        graph_version="test@1",
        status="running",
    )

    await focused.agent_message(task_id, "请补充一个例子", learner_id=learner_id)
    first_turn = await services.work_ledger.latest_turn(task_id)
    await focused.agent_message(task_id, "再简短一点", learner_id=learner_id)
    second_turn = await services.work_ledger.latest_turn(task_id)

    assert len(port.running_inputs) == 2
    assert port.running_inputs[0][2]["message"] == "请补充一个例子"
    assert first_turn is not None and second_turn is not None
    assert first_turn["id"] == second_turn["id"]
    assert port.enqueued == []


@pytest.mark.asyncio
async def test_pending_idempotency_retry_repairs_runtime_delivery(container) -> None:
    services = container
    port = _StubRuntimePort()
    focused = AgentTaskService(
        agent_task_repository=services.agent_task_repository,
        work_ledger=services.work_ledger,
        runtime_repository=services.runtime_repository,
        runtime_state=services.runtime_state,
        learner_repository=services.learner_repository,
        db=services.db,
        artifact_service=services.artifacts,
        event_service=services.agent_events,
        runtime=port,
        board_locks=defaultdict(asyncio.Lock),
    )
    learner_id = f"learner-{uuid4().hex}"
    task_id = f"task-{uuid4().hex}"
    await services.learner_repository.ensure_learner(learner_id)
    await services.agent_task_repository.create_agent_task(
        id=task_id,
        learner_id=learner_id,
        prompt="解释拥塞窗口",
        graph_version="test@1",
        status="running",
    )

    first = await focused.agent_message(
        task_id, "补充例子", learner_id=learner_id, idempotency_key="retry-delivery"
    )
    retry = await focused.agent_message(
        task_id, "补充例子", learner_id=learner_id, idempotency_key="retry-delivery"
    )

    assert first["created"] is True
    assert retry["created"] is False
    assert len(port.running_inputs) == 2, "the retry repairs append-before-delivery crashes"
    assert port.running_inputs[0][2]["command_id"] == port.running_inputs[1][2]["command_id"]
    assert len(await services.work_ledger.pending_commands(task_id)) == 1


@pytest.mark.asyncio
async def test_awaiting_user_message_is_resume_not_steering(container) -> None:
    services = container
    port = _StubRuntimePort()
    focused = AgentTaskService(
        agent_task_repository=services.agent_task_repository,
        work_ledger=services.work_ledger,
        runtime_repository=services.runtime_repository,
        runtime_state=services.runtime_state,
        learner_repository=services.learner_repository,
        db=services.db,
        artifact_service=services.artifacts,
        event_service=services.agent_events,
        runtime=port,
        board_locks=defaultdict(asyncio.Lock),
    )
    learner_id = f"learner-{uuid4().hex}"
    task_id = f"task-{uuid4().hex}"
    await services.learner_repository.ensure_learner(learner_id)
    await services.agent_task_repository.create_agent_task(
        id=task_id,
        learner_id=learner_id,
        prompt="先问我一个问题",
        graph_version="test@1",
        status="awaiting_user",
    )
    seed = await services.work_ledger.append_command(
        task_id=task_id,
        kind="initial_prompt",
        payload={"message": "先问我一个问题"},
        idempotency_key="seed-awaiting",
        delivery_mode="new_turn",
    )
    await services.work_ledger.consume_command(str(seed["id"]))

    result = await focused.agent_message(task_id, "我的回答", learner_id=learner_id)
    command = (await services.work_ledger.pending_commands(task_id))[0]

    assert result["turnId"] == seed["turn_id"] == command["turn_id"]
    assert command["delivery_mode"] == "resume"
    assert len(port.resumed) == 1
    assert port.running_inputs == []


@pytest.mark.asyncio
async def test_concurrent_idle_messages_keep_exact_command_turn_binding(container) -> None:
    services = container
    port = _StubRuntimePort()
    focused = AgentTaskService(
        agent_task_repository=services.agent_task_repository,
        work_ledger=services.work_ledger,
        runtime_repository=services.runtime_repository,
        runtime_state=services.runtime_state,
        learner_repository=services.learner_repository,
        db=services.db,
        artifact_service=services.artifacts,
        event_service=services.agent_events,
        runtime=port,
        board_locks=defaultdict(asyncio.Lock),
    )
    learner_id = f"learner-{uuid4().hex}"
    task_id = f"task-{uuid4().hex}"
    await services.learner_repository.ensure_learner(learner_id)
    await services.agent_task_repository.create_agent_task(
        id=task_id,
        learner_id=learner_id,
        prompt="旧消息",
        graph_version="test@1",
        status="completed",
    )

    results = await asyncio.gather(
        focused.agent_message(
            task_id, "第一条", learner_id=learner_id, idempotency_key="idle-1"
        ),
        focused.agent_message(
            task_id, "第二条", learner_id=learner_id, idempotency_key="idle-2"
        ),
    )
    commands = await services.work_ledger.pending_commands(task_id)
    by_message = {str(command["payload"]["message"]): command for command in commands}

    assert results[0]["turnId"] != results[1]["turnId"]
    assert {item[2]["turn_id"] for item in port.enqueued} == {
        results[0]["turnId"],
        results[1]["turnId"],
    }
    for _task, _learner, item in port.enqueued:
        command = by_message[str(item["message"])]
        assert item["command_id"] == command["id"]
        assert item["turn_id"] == command["turn_id"]


@pytest.mark.asyncio
async def test_second_adapter_delivers_ledger_owned_steering(container) -> None:
    services = container
    learner_id = f"learner-{uuid4().hex}"
    task_id = f"task-{uuid4().hex}"
    await services.learner_repository.ensure_learner(learner_id)
    await services.agent_task_repository.create_agent_task(
        id=task_id,
        learner_id=learner_id,
        prompt="解释 TCP",
        graph_version="test@1",
        status="running",
    )
    seed = await services.work_ledger.append_command(
        task_id=task_id,
        kind="initial_prompt",
        payload={"message": "解释 TCP"},
        idempotency_key="replica-seed",
        delivery_mode="new_turn",
    )
    await services.work_ledger.consume_command(str(seed["id"]))

    from lingxilearn.store.repositories.work_ledger import WorkLedgerRepository

    replica_ledger = WorkLedgerRepository(services.db)
    command = await replica_ledger.append_command(
        task_id=task_id,
        kind="message",
        payload={"message": "补充例子"},
        idempotency_key="replica-message",
        turn_id=str(seed["turn_id"]),
        delivery_mode="steering",
    )

    class Graph:
        calls: list[tuple[str, dict[str, Any]]] = []

        def steer(self, run_id: str, **kwargs: Any) -> Any:
            self.calls.append((run_id, kwargs))
            return type(
                "Steering", (), {"id": "steer-replica", "sequence": 1, "kind": "user_message"}
            )()

    graph = Graph()
    execution_id = "exec-replica-a"
    services.runtime._active_steering[task_id] = (
        graph,
        execution_id,
        execution_id,
        str(seed["turn_id"]),
    )
    delivered = await services.runtime._deliver_pending_steering_once(
        task_id, learner_id, execution_id, str(seed["turn_id"])
    )

    assert delivered == 1
    assert graph.calls[0][1]["payload"]["command_id"] == command["id"]
    replayable = (await replica_ledger.pending_commands(task_id))[0]
    assert replayable["disposition"] == "delivered"
    assert replayable["consumed_at"] is None, "delivery before checkpoint remains replayable"
    await replica_ledger.consume_command(str(command["id"]))
    assert await services.work_ledger.pending_commands(task_id) == []


@pytest.mark.asyncio
async def test_agent_event_service_owns_append_and_replay(container) -> None:
    """Event persistence/replay is constructible without the rest of the app."""

    services = container
    events = AgentEventService(
        agent_task_repository=services.agent_task_repository,
        runtime_repository=services.runtime_repository,
        work_ledger=services.work_ledger,
        runtime_state=services.runtime_state,
    )
    learner_id = f"learner-{uuid4().hex}"
    task_id = f"task-{uuid4().hex}"
    await services.learner_repository.ensure_learner(learner_id)
    await services.agent_task_repository.create_agent_task(
        id=task_id,
        learner_id=learner_id,
        prompt="讲清量子叠加",
        graph_version="test@1",
        status="queued",
    )

    await events.append(task_id, [{"kind": "task.started", "agent": "test", "payload": {}}])
    replayed = await events.events_after(task_id, learner_id, 0)
    assert [row["kind"] for row in replayed] == ["task.started"]


@pytest.mark.asyncio
async def test_artifact_service_projects_without_a_container(container, tmp_path: Path) -> None:
    """Artifact → WorkspaceFile projection needs only its own dependencies."""

    services = container
    artifacts = ArtifactResourceService(
        db=services.db,
        agent_task_repository=services.agent_task_repository,
        artifact_store=services.agent_artifacts,
        settings=services.settings,
    )
    learner_id = f"learner-{uuid4().hex}"
    task_id = f"task-{uuid4().hex}"
    await services.learner_repository.ensure_learner(learner_id)
    await services.agent_task_repository.create_agent_task(
        id=task_id,
        learner_id=learner_id,
        prompt="可视化快速排序",
        graph_version="test@1",
        status="running",
    )
    target = services.agent_artifacts.html_path(task_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("<!doctype html><html><body>demo</body></html>", encoding="utf-8")

    assert await artifacts.project_agent_artifacts(learner_id, task_id) == 1
    assert await artifacts.project_agent_artifacts(learner_id, task_id) == 0


@pytest.mark.asyncio
async def test_conversation_service_reports_unknown_session_without_container(container) -> None:
    conversation = ConversationService(
        session_repository=container.session_repository,
        runtime_state=container.runtime_state,
        learner_repository=container.learner_repository,
        learner_service=container.learners,
        packs=container.packs,
        settings=container.settings,
        graph_factory=container.graph_factory,
        tasks=container.tasks,
    )
    with pytest.raises(KeyError):
        await conversation.snapshot("s-missing", learner_id="learner-missing")


@pytest.mark.asyncio
async def test_learner_state_service_reads_profile_independently(container) -> None:
    state = LearnerStateService(runtime_state=container.runtime_state)
    assert await state.profile_for(f"learner-{uuid4().hex}") == []


def test_container_is_the_only_composition_root() -> None:
    assert ContainerServices is ApplicationServices
