from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_force_flush_runtime_callbacks_do_not_wait_for_node_boundary() -> None:
    source = (ROOT / "lingxilearn" / "application" / "runtime_adapter.py").read_text(
        encoding="utf-8"
    )
    assert "if kind in _AGENT_FORCE_FLUSH:" in source
    assert "self._tasks.spawn(flush_buffer())" in source
    assert "async with flush_lock:" in source
    assert "await persist_buffer(pending)" in source


def test_parallel_safe_work_does_not_block_serial_critical_path_start() -> None:
    source = (ROOT / "lingxilearn" / "runtime" / "nodes" / "execution.py").read_text(
        encoding="utf-8"
    )
    start = source.index("safe_future = (")
    serial = source.index("for task in serial:", start)
    join = source.index("gathered = await safe_future", serial)
    assert start < serial < join
