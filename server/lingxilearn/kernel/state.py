"""The graph state and its reducers.

Nothing in here mentions DNS, TCP or packets — the state describes *teaching*,
and the domain arrives through the course pack and the tool registry.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict


def merge_evidence(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Append new evidence, de-duplicating by id.

    A node that raises ``interrupt()`` re-runs from the top when it resumes, so
    an append-only reducer must tolerate the same entry arriving twice.
    """
    merged = list(left)
    seen = {item.get("id") for item in merged}
    for item in right:
        if item.get("id") not in seen:
            merged.append(item)
            seen.add(item.get("id"))
    return merged


def merge_tags(left: list[str], right: list[str]) -> list[str]:
    """Union of misconception tags, preserving first-seen order."""
    merged = list(left)
    for tag in right:
        if tag not in merged:
            merged.append(tag)
    return merged


def append_records(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [*left, *right]


def merge_scores(left: dict[str, float], right: dict[str, float]) -> dict[str, float]:
    return {**left, **right}


class TutorState(TypedDict, total=False):
    # --- identity ----------------------------------------------------------
    session_id: str
    learner_id: str
    pack_id: str
    pack_version: str
    mission_id: str
    mission_title: str

    # --- learner model -----------------------------------------------------
    mastery_before: dict[str, float]
    mastery: Annotated[dict[str, float], merge_scores]
    misconceptions: Annotated[list[str], merge_tags]

    # --- plan --------------------------------------------------------------
    plan: list[str]
    step_index: int
    phase: str
    current_step: dict[str, Any]

    # --- auditable trail ---------------------------------------------------
    evidence: Annotated[list[dict[str, Any]], merge_evidence]
    transcript: Annotated[list[dict[str, Any]], append_records]

    # --- current interaction ----------------------------------------------
    stage: dict[str, Any]
    move: dict[str, Any]
    last_answer: dict[str, Any]
    last_judgement: dict[str, Any]
    attempts: int
    hint_level: int
    answer_unlocked: bool
    tool_outputs: dict[str, Any]
    """Named results from the current step's tools, consumed by the graders."""
    mastery_counts: Annotated[dict[str, float], merge_scores]
    """How many graded observations back each concept — drives the learning rate."""
    mastery_changes: Annotated[list[dict[str, Any]], append_records]

    # --- assessment --------------------------------------------------------
    probe_results: Annotated[list[dict[str, Any]], append_records]
    step_results: Annotated[list[dict[str, Any]], append_records]
    verify_results: Annotated[list[dict[str, Any]], append_records]
    probe_score: float
    verify_score: float

    # --- delivery ----------------------------------------------------------
    report: dict[str, Any]
    error: dict[str, Any]


class TutorContext(TypedDict, total=False):
    """Per-run context (not persisted in the checkpoint)."""

    learner_id: str
    locale: str


def initial_state(
    *,
    session_id: str,
    learner_id: str,
    pack_id: str,
    pack_version: str,
    mission_id: str,
    mastery: dict[str, float] | None = None,
) -> TutorState:
    known = dict(mastery or {})
    return TutorState(
        session_id=session_id,
        learner_id=learner_id,
        pack_id=pack_id,
        pack_version=pack_version,
        mission_id=mission_id,
        mission_title="",
        mastery_before=dict(known),
        mastery=dict(known),
        misconceptions=[],
        plan=[],
        step_index=0,
        phase="intake",
        current_step={},
        evidence=[],
        transcript=[],
        stage={},
        move={},
        last_answer={},
        last_judgement={},
        attempts=0,
        hint_level=0,
        answer_unlocked=False,
        tool_outputs={},
        mastery_counts={},
        mastery_changes=[],
        probe_results=[],
        step_results=[],
        verify_results=[],
        probe_score=0.0,
        verify_score=0.0,
        report={},
        error={},
    )
