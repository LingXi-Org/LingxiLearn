from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_service() -> None:
    path = Path("server/lingxilearn/service.py")
    replace_once(
        path,
        '''        buffer: list[dict[str, Any]] = []
        current_agent = "coordinator"
        graph: Any | None = None

        def emit_runtime_event(kind: str, payload: dict[str, Any]) -> None:
            agent = str(payload.pop("agent", "orchestrator"))
            projected = projector.consume_runtime_event(kind, payload, agent=agent)
            projected["execution_id"] = execution_id
            buffer.append(projected)
''',
        '''        buffer: list[dict[str, Any]] = []
        current_agent = "coordinator"
        graph: Any | None = None
        flush_lock = asyncio.Lock()

        async def flush_buffer() -> None:
            """Persist buffered learner events immediately and in sequence.

            Runtime callbacks execute inside graph nodes while native stream
            events are consumed by the outer iterator. Both paths append to
            this buffer, so every flush is serialized through one lock.
            """

            async with flush_lock:
                if not buffer:
                    return
                pending = list(buffer)
                buffer.clear()
                await persist_buffer(pending)

        def emit_runtime_event(kind: str, payload: dict[str, Any]) -> None:
            agent = str(payload.pop("agent", "orchestrator"))
            projected = projector.consume_runtime_event(kind, payload, agent=agent)
            projected["execution_id"] = execution_id
            buffer.append(projected)
            # deps.emit is synchronous and bypasses the native CUSTOM stream.
            # Force-flush learner output and AgentRun identity now instead of
            # waiting for a model/node boundary to make the outer loop wake up.
            if kind in _AGENT_FORCE_FLUSH:
                self._spawn(flush_buffer())
''',
    )
    replace_once(
        path,
        '''                    if len(buffer) >= AGENT_FLUSH_EVERY:
                        await persist_buffer(list(buffer))
                        buffer.clear()
''',
        '''                    if len(buffer) >= AGENT_FLUSH_EVERY:
                        await flush_buffer()
''',
    )
    replace_once(
        path,
        '''                if force_flush or len(buffer) >= AGENT_FLUSH_EVERY:
                    await persist_buffer(list(buffer))
                    buffer.clear()
''',
        '''                if force_flush or len(buffer) >= AGENT_FLUSH_EVERY:
                    await flush_buffer()
''',
    )
    replace_once(
        path,
        '''            await persist_buffer(buffer)
            buffer.clear()
''',
        '''            await flush_buffer()
''',
    )
    replace_once(
        path,
        '''        if buffer:
            await persist_buffer(buffer)
''',
        '''        # Join any in-flight forced flush before terminal state is read.
        await flush_buffer()
''',
    )
    replace_once(
        path,
        '''                if current_record.status == "cancelled":
                    snapshot = projector.snapshot()
''',
        '''                if current_record.status == "cancelled":
                    await flush_buffer()
                    snapshot = projector.snapshot()
''',
    )


def patch_loop() -> None:
    path = Path("server/lingxilearn/runtime/loop.py")
    replace_once(
        path,
        '''            results: list[TaskOutcome] = []
            if safe:
                gathered = await asyncio.gather(
                    *(dispatcher.run(task, profile=profile_rows, budget=budget) for task in safe),
                    return_exceptions=True,
                )
                results.extend(
                    item
                    if isinstance(item, TaskOutcome)
                    else TaskOutcome(
                        task_id=safe[index].id,
                        capability=safe[index].capability,
                        status="failed",
                        detail=f"{type(item).__name__}: {item}",
                    )
                    for index, item in enumerate(gathered)
                )
            for task in serial:
                results.append(await dispatcher.run(task, profile=profile_rows, budget=budget))
''',
        '''            results: list[TaskOutcome] = []
            # Start independent safe work immediately, but never await that
            # whole batch before the learner-facing serial critical path starts.
            safe_future = (
                asyncio.gather(
                    *(dispatcher.run(task, profile=profile_rows, budget=budget) for task in safe),
                    return_exceptions=True,
                )
                if safe
                else None
            )
            try:
                for task in serial:
                    results.append(await dispatcher.run(task, profile=profile_rows, budget=budget))
            finally:
                # Same-tier tasks have no dependency edges between them. Join
                # before the next tier so dependency semantics remain intact.
                if safe_future is not None:
                    gathered = await safe_future
                    results.extend(
                        item
                        if isinstance(item, TaskOutcome)
                        else TaskOutcome(
                            task_id=safe[index].id,
                            capability=safe[index].capability,
                            status="failed",
                            detail=f"{type(item).__name__}: {item}",
                        )
                        for index, item in enumerate(gathered)
                    )
''',
    )


def add_regression_tests() -> None:
    path = Path("server/tests/test_slow_first_token_regression.py")
    path.write_text(
        '''from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_force_flush_runtime_callbacks_do_not_wait_for_node_boundary() -> None:
    source = (ROOT / "lingxilearn" / "service.py").read_text(encoding="utf-8")
    assert "if kind in _AGENT_FORCE_FLUSH:" in source
    assert "self._spawn(flush_buffer())" in source
    assert "async with flush_lock:" in source
    assert "await persist_buffer(pending)" in source


def test_parallel_safe_work_does_not_block_serial_critical_path_start() -> None:
    source = (ROOT / "lingxilearn" / "runtime" / "loop.py").read_text(encoding="utf-8")
    start = source.index("safe_future = (")
    serial = source.index("for task in serial:", start)
    join = source.index("gathered = await safe_future", serial)
    assert start < serial < join
''',
        encoding="utf-8",
    )


if __name__ == "__main__":
    patch_service()
    patch_loop()
    add_regression_tests()
