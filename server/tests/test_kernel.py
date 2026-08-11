"""The teaching loop itself: real graph, real interrupts, real grading."""

from __future__ import annotations

import pytest
from lingxigraph import Command, InMemorySaver

from lingxilearn.brains.scripted import ScriptedBrain
from lingxilearn.kernel.evidence import Ledger, verify_citations
from lingxilearn.kernel.graph import build_graph
from lingxilearn.kernel.state import initial_state, merge_evidence, merge_tags
from lingxilearn.packs.loader import validate_pack
from lingxilearn.tools import knowledge

TRUTH = {"dns": 121.4, "tcp_connect": 31.9, "ttfb": 188.6, "transfer": 19.2, "retransmission": 225.8}
PINS = {
    "dns": [1, 2], "tcp_connect": [3, 4, 5], "ttfb": [6, 7],
    "transfer": [8, 9, 10], "retransmission": [12, 13, 14],
}
RIGHT = {"p1": "a", "p2": "b", "p3": "b", "v1": "c", "v2": "b", "orient": "b", "stall": "b"}
WRONG = {"p1": "b", "p2": "a", "p3": "a", "orient": "a", "stall": "a"}


@pytest.fixture
def graph(pack, registry, pack_dir):
    knowledge.configure([pack_dir / "knowledge"])
    return build_graph(
        pack=pack, brain=ScriptedBrain(), registry=registry, checkpointer=InMemorySaver()
    )


def config_for(pack, thread: str) -> dict:
    return {"configurable": {"thread_id": thread, "checkpoint_ns": pack.checkpoint_ns}}


def start_state(pack, thread: str, mission: str = "web-slow"):
    return initial_state(
        session_id=thread,
        learner_id="test",
        pack_id=pack.id,
        pack_version=pack.version,
        mission_id=mission,
    )


async def drive(graph, pack, thread, answer_fn, *, mission="web-slow", limit=30):
    """Run to completion, recording every pause the learner saw."""
    config = config_for(pack, thread)
    result = await graph.ainvoke(start_state(pack, thread, mission), config)
    pauses = []
    turns = 0
    while "__interrupt__" in result and turns < limit:
        turns += 1
        payload = result["__interrupt__"][0].value
        pauses.append(payload)
        result = await graph.ainvoke(Command(resume=answer_fn(payload, turns)), config)
    snapshot = await graph.aget_state(config)
    return snapshot.values, pauses


# --------------------------------------------------------------------------


def test_pack_is_structurally_valid(pack, registry):
    result = validate_pack(pack, registry)
    assert result.valid, [f"{i.code}@{i.path}" for i in result.issues]


async def test_confident_learner_completes_the_mission(graph, pack):
    def answer(payload, _turn):
        if payload["kind"] in ("probe", "verify"):
            return {i["id"]: {"choice": RIGHT[i["id"]]} for i in payload["items"]}
        expects = payload["prompt"]["expects"]
        if expects == "attribution":
            return {"allocations": TRUTH, "pins": PINS}
        return {"choice": RIGHT[payload["step_id"]]}

    final, pauses = await drive(graph, pack, "t-ideal", answer)
    assert final["phase"] == "done"
    assert final["report"]["verify_score"] == 1.0
    assert [p["kind"] for p in pauses][0] == "probe"
    assert "verify" in [p["kind"] for p in pauses]


async def test_wrong_answer_escalates_hints_without_leaking(graph, pack):
    """The core promise: keep coaching, never hand over the answer."""

    def answer(payload, _turn):
        if payload["kind"] in ("probe", "verify"):
            table = RIGHT if payload["kind"] == "verify" else WRONG
            return {i["id"]: {"choice": table.get(i["id"], "a")} for i in payload["items"]}
        expects = payload["prompt"]["expects"]
        if expects == "attribution":
            # Always wrong: blame the server, ignore the retransmission.
            return {
                "allocations": {**TRUTH, "ttfb": 400.0, "retransmission": 0.0},
                "pins": PINS,
            }
        return {"choice": WRONG.get(payload["step_id"], "a")}

    final, pauses = await drive(graph, pack, "t-wrong", answer)
    answer_pauses = [p for p in pauses if p["kind"] == "answer"]
    levels = [p["hint_level"] for p in answer_pauses]
    assert max(levels) > 0, "hints never escalated"

    assert "transfer_time_as_server_think" in final["misconceptions"]

    # No coaching turn may contain a guarded value while the answer is locked.
    for pause in answer_pauses:
        if pause["prompt"].get("intent") == "reveal":
            continue
        said = pause["prompt"]["say"]
        assert "225.8" not in said and "188.6" not in said, said


async def test_two_learners_get_different_paths_on_one_mission(graph, pack, registry):
    """因材施教, demonstrated rather than asserted: mastery changes the plan."""
    strong = initial_state(
        session_id="t-strong",
        learner_id="strong",
        pack_id=pack.id,
        pack_version=pack.version,
        mission_id="web-slow",
        mastery={"dns.resolution": 0.95, "tcp.handshake": 0.95},
    )
    config = config_for(pack, "t-strong")
    result = await graph.ainvoke(strong, config)
    payload = result["__interrupt__"][0].value
    result = await graph.ainvoke(
        Command(resume={i["id"]: {"choice": RIGHT[i["id"]]} for i in payload["items"]}), config
    )
    strong_plan = (await graph.aget_state(config)).values["plan"]

    weak_final, _ = await drive(
        graph,
        pack,
        "t-weak",
        lambda payload, turn: (
            {i["id"]: {"choice": WRONG.get(i["id"], "a")} for i in payload["items"]}
            if payload["kind"] in ("probe", "verify")
            else (
                {"allocations": TRUTH, "pins": PINS}
                if payload["prompt"]["expects"] == "attribution"
                else {"choice": RIGHT[payload["step_id"]]}
            )
        ),
    )
    assert "orient" not in strong_plan, "a strong learner should skip the warm-up"
    assert "orient" in weak_final["plan"], "a weak learner needs the warm-up"


async def test_every_report_claim_resolves_to_real_evidence(graph, pack):
    def answer(payload, _turn):
        if payload["kind"] in ("probe", "verify"):
            return {i["id"]: {"choice": RIGHT[i["id"]]} for i in payload["items"]}
        if payload["prompt"]["expects"] == "attribution":
            return {"allocations": TRUTH, "pins": PINS}
        return {"choice": RIGHT[payload["step_id"]]}

    final, _ = await drive(graph, pack, "t-cite", answer)
    evidence = final["evidence"]
    assert evidence
    for claim, ids in final["report"]["citations"].items():
        assert not verify_citations(evidence, ids), f"dangling citation on: {claim}"


async def test_simulator_mission_runs_through_the_same_kernel(graph, pack):
    from lingxilearn.tools.net import sim

    table = {"p1": "b", "p2": "b", "p3": "b", "v1": "b", "v2": "b",
             "read-the-console": "a", "debrief": "b"}

    def answer(payload, _turn):
        if payload["kind"] in ("probe", "verify"):
            return {i["id"]: {"choice": table[i["id"]]} for i in payload["items"]}
        if payload["prompt"]["expects"] == "sim_action":
            return {"actions": sim.oracle("single-loss", 7)["actions"]}
        return {"choice": table[payload["step_id"]]}

    final, _ = await drive(graph, pack, "t-sim", answer, mission="reliable-delivery")
    assert final["phase"] == "done"
    assert any(e["kind"] == "simulation_frame" for e in final["evidence"])


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
    first = ledger.add(kind="tool_result", source="net.pcap.waterfall", summary="x", value={"a": 1})
    second = ledger.add(kind="tool_result", source="net.pcap.waterfall", summary="x", value={"a": 1})
    assert first.id == second.id
    assert len(ledger.entries) == 1


def test_ledger_separates_different_content_from_the_same_tool():
    ledger = Ledger()
    a = ledger.add(kind="tool_result", source="t", summary="x", value={"a": 1})
    b = ledger.add(kind="tool_result", source="t", summary="x", value={"a": 2})
    assert a.id != b.id and a.digest != b.digest
