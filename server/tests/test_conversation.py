from pathlib import Path

from lingxilearn.runtime.candidates import WorldState
from lingxilearn.runtime.contracts import CandidateAction
from lingxilearn.runtime.orchestrator import _repair
from lingxilearn.service import _SidecarRuntime
from lingxilearn.state.capabilities import Capability
from lingxilearn.state.gain import ProfileView
from lingxilearn.state.session_state import Goal
from lingxilearn.state.skill_catalog import discover

SKILLS = Path(__file__).resolve().parents[2] / "skills"


def test_realtime_conversation_capabilities_are_registry_backed() -> None:
    manifests = {manifest.skill_id: manifest for manifest in discover(SKILLS)}
    assert str(Capability.DIALOG_CONVERSE) in {
        str(capability) for capability in manifests["learning-companion"].capabilities
    }
    assert str(Capability.DIALOG_PROBE) in {
        str(capability) for capability in manifests["socratic-prober"].capabilities
    }
    assert manifests["learning-companion"].cost["blocking"] is True
    assert str(Capability.DIALOG_INTERVIEW) in {
        str(capability) for capability in manifests["learner-interview"].capabilities
    }


def test_every_discovered_skill_has_a_user_safe_status_line() -> None:
    assert all(manifest.status_line.strip() for manifest in discover(SKILLS))


def test_sidecar_runtime_preserves_learner_facing_output() -> None:
    runtime = _SidecarRuntime("dialog.converse")

    runtime.emit(
        "agent_task",
        {
            "type": "agent.output",
            "agent": "learning_companion",
            "stream_id": "task:dialog.converse:t1",
            "message": "我已经收到你的问题，正在继续处理。",
        },
    )

    assert runtime.events == [
        {
            "kind": "agent.output",
            "agent": "learning_companion",
            "payload": {
                "stream_id": "task:dialog.converse:t1",
                "message": "我已经收到你的问题，正在继续处理。",
            },
        }
    ]


def test_new_learner_plan_keeps_opening_conversation_present() -> None:
    candidate = CandidateAction(
        capability=str(Capability.DIALOG_INTERVIEW),
        skill_id="learner-interview",
        provider="learner_interview",
        knowledge_point_id="kp-1",
        gain=0.5,
        utility=0.5,
        reason="先了解学习起点",
        parallel_safe=False,
        critical_path=True,
    )
    plan = _repair(
        {"tasks": [], "awaits_user": True},
        goal=Goal(goal_type="learn", topic="TCP", knowledge_points=("kp-1",)),
        world=WorldState(target=ProfileView.unseen("kp-1")),
        candidates=[candidate],
    )

    assert plan is not None
    assert [task.capability for task in plan.tasks] == [str(Capability.DIALOG_INTERVIEW)]


def test_interview_is_forced_until_its_result_is_persisted() -> None:
    candidate = CandidateAction(
        capability=str(Capability.DIALOG_INTERVIEW),
        skill_id="learner-interview",
        provider="learner_interview",
        knowledge_point_id="kp-1",
        gain=0.1,
        utility=0.1,
        reason="了解学习起点",
        critical_path=True,
    )
    goal = Goal(goal_type="learn", topic="TCP", knowledge_points=("kp-1",))
    with_interview = WorldState(
        target=ProfileView.unseen("kp-1"), interview_completed=True
    )
    plan = _repair(
        {"tasks": [], "awaits_user": True},
        goal=goal,
        world=with_interview,
        candidates=[candidate],
    )

    assert plan is not None
    assert plan.tasks == []
