"""The teaching loop itself: real graph, real interrupts, real grading."""

from __future__ import annotations

from lingxilearn.kernel.evidence import Ledger
from lingxilearn.kernel.state import merge_evidence, merge_tags

# --------------------------------------------------------------------------
# Reducers and the ledger
# --------------------------------------------------------------------------


def test_evidence_reducer_tolerates_a_replayed_node():
    """A node that interrupts re-runs on resume; its appends must not duplicate."""
    left = [{"id": "ev_0001"}, {"id": "ev_0002"}]
    assert merge_evidence(left, [{"id": "ev_0002"}, {"id": "ev_0003"}]) == [
        {"id": "ev_0001"},
        {"id": "ev_0002"},
        {"id": "ev_0003"},
    ]


def test_tag_reducer_is_a_stable_union():
    assert merge_tags(["a", "b"], ["b", "c"]) == ["a", "b", "c"]


def test_ledger_is_idempotent_for_identical_content():
    ledger = Ledger()
    first = ledger.add(kind="tool_result", source="course.tool", summary="x", value={"a": 1})
    second = ledger.add(kind="tool_result", source="course.tool", summary="x", value={"a": 1})
    assert first.id == second.id
    assert len(ledger.entries) == 1


def test_ledger_separates_different_content_from_the_same_tool():
    ledger = Ledger()
    a = ledger.add(kind="tool_result", source="t", summary="x", value={"a": 1})
    b = ledger.add(kind="tool_result", source="t", summary="x", value={"a": 2})
    assert a.id != b.id and a.digest != b.digest
