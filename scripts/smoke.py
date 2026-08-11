#!/usr/bin/env python3
"""End-to-end smoke test: drive a whole mission with a scripted learner.

    python scripts/smoke.py --mission web-slow --learner ideal
    python scripts/smoke.py --mission reliable-delivery --learner confused

Exercises the real graph — real checkpointer, real interrupts, real tools, real
grading — with no network and no API key.  Two learner personas drive the same
mission down different paths, which is the point: ``confused`` should trip a
named misconception and climb the hint ladder, ``ideal`` should not.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "server"))

from lingxigraph import Command, SqliteSaver  # noqa: E402

from lingxilearn.brains.scripted import ScriptedBrain  # noqa: E402
from lingxilearn.kernel.graph import build_graph  # noqa: E402
from lingxilearn.kernel.state import initial_state  # noqa: E402
from lingxilearn.packs.loader import load_pack  # noqa: E402
from lingxilearn.tools import knowledge  # noqa: E402
from lingxilearn.tools.net import sim  # noqa: E402
from lingxilearn.tools.registry import load_builtin_tools  # noqa: E402

PASS, FAIL = "[PASS]", "[FAIL]"
_failures: list[str] = []


def check(condition: bool, label: str, detail: str = "") -> None:
    print(f"{PASS if condition else FAIL} {label}" + (f"  — {detail}" if detail else ""))
    if not condition:
        _failures.append(label)


# --------------------------------------------------------------------------
# Scripted learners
# --------------------------------------------------------------------------

TRUTH = {"dns": 121.4, "tcp_connect": 31.9, "ttfb": 188.6, "transfer": 19.2, "retransmission": 225.8}
PINS = {
    "dns": [1, 2],
    "tcp_connect": [3, 4, 5],
    "ttfb": [6, 7],
    "transfer": [8, 9, 10],
    "retransmission": [12, 13, 14],
}

# The classic wrong answer: the retransmission stall gets filed as server slowness.
CONFUSED_ALLOC = {
    "dns": 121.0,
    "tcp_connect": 32.0,
    "ttfb": 400.0,
    "transfer": 30.0,
    "retransmission": 0.0,
}

# Item ids repeat across missions (every mission has a p1), so the answer keys
# are scoped by mission.
IDEAL_CHOICES = {
    "web-slow": {
        "p1": "a", "p2": "b", "p3": "b",
        "v1": "c", "v2": "b",
        "orient": "b", "stall": "b",
    },
    "reliable-delivery": {
        "p1": "b", "p2": "b", "p3": "b",
        "v1": "b", "v2": "b",
        "read-the-console": "a", "debrief": "b",
    },
}
# The confused learner arrives with the classic wrong models, works through the
# hint ladder, and — this is the part being tested — answers the *post*-test
# correctly. A tutor that produces no measurable learning gain has not taught.
CONFUSED_CHOICES = {
    "web-slow": {
        "p1": "b", "p2": "a", "p3": "a",
        "v1": "c", "v2": "b",
        "orient": "a", "stall": "a",
    },
    "reliable-delivery": {
        "p1": "a", "p2": "a", "p3": "c",
        "v1": "b", "v2": "b",
        "read-the-console": "b", "debrief": "a",
    },
}


def good_sim_actions() -> list[dict[str, Any]]:
    return sim.oracle("single-loss", 7)["actions"]


def bad_sim_actions() -> list[dict[str, Any]]:
    """Never fast-retransmits; blasts the whole window when it finally reacts."""
    return (
        [{"op": "send"}] * 4
        + [{"op": "wait"}] * 10
        + [{"op": "retransmit_all"}]
        + [{"op": "wait"}] * 12
        + [{"op": "send"}] * 4
        + [{"op": "wait"}] * 40
    )


def answer_for(
    payload: dict[str, Any], persona: str, attempt_counts: dict[str, int], mission: str
) -> Any:
    kind = payload.get("kind")
    source = IDEAL_CHOICES if persona == "ideal" else CONFUSED_CHOICES
    table = source.get(mission, {})
    ideal = IDEAL_CHOICES.get(mission, {})

    if kind in ("probe", "verify"):
        return {item["id"]: {"choice": table.get(item["id"], "a")} for item in payload["items"]}

    step_id = payload.get("step_id", "")
    seen = attempt_counts.get(step_id, 0)
    attempt_counts[step_id] = seen + 1
    expects = (payload.get("prompt") or {}).get("expects", "text")

    if expects == "attribution":
        if persona == "ideal":
            return {"allocations": dict(TRUTH), "pins": dict(PINS)}
        # The confused learner corrects itself once the ladder has done its work.
        if seen >= 2:
            return {"allocations": dict(TRUTH), "pins": dict(PINS)}
        return {"allocations": dict(CONFUSED_ALLOC), "pins": dict(PINS)}

    if expects == "sim_action":
        if persona == "ideal" or seen >= 2:
            return {"actions": good_sim_actions()}
        return {"actions": bad_sim_actions()}

    if expects == "choice":
        if persona == "confused" and seen >= 2:
            return {"choice": ideal.get(step_id, "b")}
        return {"choice": table.get(step_id, "a")}

    return {"text": "我先按证据推一遍。"}


# --------------------------------------------------------------------------


async def run(mission_id: str, persona: str, pack_dir: Path) -> int:
    pack = load_pack(pack_dir)
    registry = load_builtin_tools()
    knowledge.configure([pack_dir / "knowledge"])

    workdir = Path(tempfile.mkdtemp(prefix="lingxilearn-smoke-"))
    saver = SqliteSaver(str(workdir / "checkpoints.sqlite3"))
    graph = build_graph(pack=pack, brain=ScriptedBrain(), registry=registry, checkpointer=saver)
    check(True, "graph compiled", f"nodes={len(graph.get_graph().nodes)}")

    thread_id = f"smoke-{mission_id}-{persona}"
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": pack.checkpoint_ns}}
    state = initial_state(
        session_id=thread_id,
        learner_id=f"demo-{persona}",
        pack_id=pack.id,
        pack_version=pack.version,
        mission_id=mission_id,
    )

    attempts: dict[str, int] = {}
    payload_kinds: list[str] = []
    hint_levels: list[int] = []
    tool_calls = 0
    guarded = 0

    result = await graph.ainvoke(state, config, context={"learner_id": f"demo-{persona}"})
    turns = 0
    while "__interrupt__" in result and turns < 40:
        turns += 1
        marker = result["__interrupt__"][0]
        payload = marker.value if isinstance(marker.value, dict) else {}
        payload_kinds.append(str(payload.get("kind")))
        if payload.get("kind") == "answer":
            hint_levels.append(int(payload.get("hint_level", 0)))
        reply = answer_for(payload, persona, attempts, mission_id)
        result = await graph.ainvoke(Command(resume=reply), config)

    check("__interrupt__" not in result, "mission ran to completion", f"{turns} learner turns")
    check("probe" in payload_kinds, "pre-test presented")
    check("answer" in payload_kinds, "socratic loop entered (HITL)")
    check("verify" in payload_kinds, "post-test presented")

    snapshot = await graph.aget_state(config)
    final = snapshot.values
    evidence = final.get("evidence", [])
    report = final.get("report", {})

    for entry in evidence:
        if entry["kind"] == "tool_result":
            tool_calls += 1
    check(tool_calls > 0, "real tools ran", f"{tool_calls} tool results in the ledger")
    check(
        any(e["kind"] == "knowledge" for e in evidence),
        "knowledge citations captured",
        f"{sum(1 for e in evidence if e['kind'] == 'knowledge')} chunks",
    )
    check(bool(report), "learning report produced")
    check(
        report.get("evidence_count", 0) == len(evidence),
        "report evidence count matches the ledger",
        f"{len(evidence)} entries",
    )

    known = {e["id"] for e in evidence}
    dangling = [
        cid for ids in report.get("citations", {}).values() for cid in ids if cid not in known
    ]
    check(not dangling, "every report citation resolves", f"{len(report.get('citations', {}))} claims")

    if persona == "confused":
        check(bool(final.get("misconceptions")), "misconception detected",
              ", ".join(final.get("misconceptions", [])))
        check(max(hint_levels or [0]) > 0, "hint ladder escalated",
              f"max level {max(hint_levels or [0])}")
        check(
            report.get("learning_gain", 0) > 0,
            "learning gain measured",
            f"probe {report.get('probe_score')} → verify {report.get('verify_score')}",
        )
    else:
        check(
            report.get("verify_score", 0) >= 0.9,
            "ideal learner passes the post-test",
            f"verify {report.get('verify_score')}",
        )

    steps_done = final.get("step_results", [])
    check(bool(steps_done), "teaching steps recorded", f"{len(steps_done)} steps")

    # Durability: a fresh graph object must resume the same thread from disk.
    reopened = build_graph(
        pack=pack, brain=ScriptedBrain(), registry=registry, checkpointer=saver
    )
    restored = await reopened.aget_state(config)
    check(
        restored.values.get("phase") == "done"
        and len(restored.values.get("evidence", [])) == len(evidence),
        "session restored from checkpoint",
        f"phase={restored.values.get('phase')}",
    )

    print()
    print(f"  mission        : {final.get('mission_title')}")
    print(f"  probe → verify : {report.get('probe_score'):.0%} → {report.get('verify_score'):.0%}"
          f"  (gain {report.get('learning_gain', 0):+.0%})")
    print(f"  mastery        : {report.get('mastery_after')}")
    print(f"  misconceptions : {final.get('misconceptions') or '—'}")
    print(f"  evidence       : {len(evidence)} entries")
    print(f"  headline       : {report.get('headline')}")
    _ = guarded
    return 1 if _failures else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mission", default="web-slow")
    parser.add_argument("--learner", default="confused", choices=["ideal", "confused"])
    parser.add_argument("--pack", default=str(REPO_ROOT / "packs/computer-networks"))
    args = parser.parse_args()

    print(f"=== LingxiLearn smoke · mission={args.mission} learner={args.learner} ===")
    code = asyncio.run(run(args.mission, args.learner, Path(args.pack)))
    print()
    print("RESULT:", "FAILED — " + ", ".join(_failures) if _failures else "all checks passed")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
