"""Learning-gain evaluation, computed from the trace."""

from __future__ import annotations

from lingxilearn.eval.learning_gain import (
    evaluate_task,
    mastery_gain,
    misconception_resolution,
    prerequisite_closure,
)


def decision(step: int, before: dict, after: dict, **extra) -> dict:
    return {
        "step": step,
        "profile_before": before,
        "profile_after": after,
        "evidence_ids": extra.pop("evidence_ids", ["ev_1"]),
        "replan_of": extra.pop("replan_of", None),
        **extra,
    }


def point(mastery: float, **extra) -> dict:
    return {"mastery": mastery, "misconceptions": [], "prerequisites": [], **extra}


def test_gain_is_measured_end_to_end_not_summed_per_round() -> None:
    """Churn inside a task must not inflate the total."""

    decisions = [
        decision(1, {"tcp": point(0.30)}, {"tcp": point(0.50)}),
        decision(2, {"tcp": point(0.50)}, {"tcp": point(0.40)}),
        decision(3, {"tcp": point(0.40)}, {"tcp": point(0.62)}),
    ]
    assert mastery_gain(decisions) == {"tcp": 0.32}


def test_efficiency_is_gain_per_evidence_not_gain_per_turn() -> None:
    decisions = [decision(1, {"tcp": point(0.30)}, {"tcp": point(0.60)})]
    report = evaluate_task("t1", decisions, evidence=[{}, {}, {}])
    assert report.mastery_gain == 0.30
    assert report.gain_per_evidence == 0.1
    assert report.gain_per_step == 0.30


def test_a_regression_is_reported_not_hidden() -> None:
    decisions = [decision(1, {"tcp": point(0.70)}, {"tcp": point(0.40)})]
    report = evaluate_task("t1", decisions)
    assert report.mastery_gain < 0
    assert report.points_regressed == 1
    assert report.points_improved == 0


def test_unsourced_profile_movement_is_counted_as_a_defect() -> None:
    """The single-writer rule makes this impossible; measure it anyway."""

    clean = [decision(1, {"tcp": point(0.3)}, {"tcp": point(0.6)}, evidence_ids=["ev_1"])]
    assert evaluate_task("t1", clean).unsourced_changes == 0

    leaked = [decision(1, {"tcp": point(0.3)}, {"tcp": point(0.6)}, evidence_ids=[])]
    assert evaluate_task("t1", leaked).unsourced_changes == 1


def test_replans_are_counted() -> None:
    decisions = [
        decision(1, {}, {"tcp": point(0.3)}),
        decision(2, {"tcp": point(0.3)}, {"tcp": point(0.4)}, replan_of="dec_1"),
    ]
    assert evaluate_task("t1", decisions).replan_count == 1


def test_diagnosing_a_prerequisite_without_fixing_it_scores_zero() -> None:
    """Noticing a gap and moving on is diagnosis, not teaching."""

    decisions = [
        decision(
            1,
            {
                "tcp": point(0.3, prerequisites=["window"]),
                "window": point(0.2),
            },
            {"tcp": point(0.3, prerequisites=["window"]), "window": point(0.2)},
        )
    ]
    assert prerequisite_closure(decisions) == 0.0

    decisions.append(
        decision(
            2,
            {"tcp": point(0.3, prerequisites=["window"]), "window": point(0.2)},
            {"tcp": point(0.5, prerequisites=["window"]), "window": point(0.8)},
        )
    )
    assert prerequisite_closure(decisions) == 1.0


def test_no_prerequisites_is_full_closure_not_zero() -> None:
    assert prerequisite_closure([decision(1, {"tcp": point(0.3)}, {"tcp": point(0.5)})]) == 1.0


def test_misconception_resolution_requires_the_tag_to_be_gone() -> None:
    lingering = [
        decision(
            1,
            {"tcp": point(0.3, misconceptions=["cwnd 与 rwnd 混淆"])},
            {"tcp": point(0.5, misconceptions=["cwnd 与 rwnd 混淆"])},
        )
    ]
    assert misconception_resolution(lingering) == 0.0

    resolved = [
        *lingering,
        decision(
            2,
            {"tcp": point(0.5, misconceptions=["cwnd 与 rwnd 混淆"])},
            {"tcp": point(0.7, misconceptions=[])},
        ),
    ]
    assert misconception_resolution(resolved) == 1.0


def test_the_report_carries_no_satisfaction_metric() -> None:
    """The metric is learning gain. Enjoying a session is not learning."""

    payload = evaluate_task("t1", [decision(1, {}, {"tcp": point(0.5)})]).to_dict()
    banned = {"satisfaction", "rating", "sentiment", "thumbs", "nps", "helpfulness"}
    assert not banned & set(payload)


def test_an_empty_task_scores_zero_without_dividing_by_zero() -> None:
    report = evaluate_task("t1", [])
    assert report.mastery_gain == 0.0
    assert report.gain_per_evidence == 0.0
    assert report.gain_per_step == 0.0
