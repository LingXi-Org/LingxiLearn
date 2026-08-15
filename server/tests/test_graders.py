"""Grading is computed, never judged — so it is testable to the decimal."""

from __future__ import annotations

from lingxilearn.kernel.graders import grade

TRUTH = {
    "total_ms": 604.6,
    "buckets": {
        "dns": 121.4,
        "tcp_connect": 31.9,
        "ttfb": 188.6,
        "transfer": 19.2,
        "retransmission": 225.8,
    },
    "bucket_frames": {
        "dns": [1, 2],
        "tcp_connect": [3, 4, 5],
        "ttfb": [6, 7],
        "transfer": [7, 8, 9, 10],
        "retransmission": [12, 13, 14],
    },
}

SPEC = {
    "kind": "attribution",
    "truth_from": "waterfall",
    "tolerance_ratio": 0.08,
    "tolerance_floor_ms": 15,
    "threshold": 0.8,
    "require_pins": True,
    "confusion_threshold_ratio": 0.1,
    "confusions": [
        {
            "over": "ttfb",
            "under": "retransmission",
            "misconception": "transfer_time_as_server_think",
        }
    ],
    "pin_misconceptions": {"dns": "pins_do_not_support_claim"},
    "concepts": ["perf.attribution"],
}
CTX = {"tools": {"waterfall": TRUTH}}

GOOD_PINS = {
    "dns": [1, 2],
    "tcp_connect": [3, 4, 5],
    "ttfb": [6, 7],
    "transfer": [8, 9],
    "retransmission": [13, 14],
}


def test_correct_attribution_passes():
    answer = {"allocations": dict(TRUTH["buckets"]), "pins": GOOD_PINS}
    result = grade(SPEC, answer, CTX)
    assert result.correct and result.score == 1.0


def test_percentages_are_accepted_as_well_as_milliseconds():
    total = TRUTH["total_ms"]
    answer = {
        "allocations": {k: v / total * 100 for k, v in TRUTH["buckets"].items()},
        "pins": GOOD_PINS,
    }
    assert grade(SPEC, answer, CTX).correct


def test_blaming_the_server_is_named_as_a_specific_misconception():
    """The classic error: the retransmission stall filed as server think time."""
    answer = {
        "allocations": {
            "dns": 121.4,
            "tcp_connect": 31.9,
            "ttfb": 400.0,
            "transfer": 30.0,
            "retransmission": 0.0,
        },
        "pins": GOOD_PINS,
    }
    result = grade(SPEC, answer, CTX)
    assert not result.correct
    assert "transfer_time_as_server_think" in result.misconceptions


def test_right_number_with_a_wrong_frame_still_fails():
    """A conclusion is only as good as the evidence pinned to it."""
    answer = {
        "allocations": dict(TRUTH["buckets"]),
        "pins": {**GOOD_PINS, "dns": [9]},  # frame 9 is response data, not DNS
    }
    result = grade(SPEC, answer, CTX)
    assert not result.correct
    assert "pins_do_not_support_claim" in result.misconceptions
    assert result.detail["buckets"]["dns"]["invalid_pins"] == [9]


def test_missing_truth_fails_loudly_rather_than_silently_passing():
    result = grade(SPEC, {"allocations": {}, "pins": {}}, {"tools": {}})
    assert not result.correct
    assert result.detail["error"] == "missing_truth"


def test_choice_grader_maps_a_distractor_to_its_misconception():
    spec = {
        "kind": "choice",
        "answer": "b",
        "misconceptions": {"a": "ttfb_ignores_server_time"},
        "concepts": ["http.ttfb"],
    }
    assert grade(spec, {"choice": "b"}).correct
    wrong = grade(spec, {"choice": "a"})
    assert not wrong.correct
    assert wrong.misconceptions == ["ttfb_ignores_server_time"]


def test_sim_outcome_requires_correctness_before_efficiency():
    spec = {"kind": "sim_outcome", "score_from": "score", "min_efficiency": 0.6}
    fast_but_broken = {
        "tools": {"score": {"delivered_intact": False, "efficiency": 1.0, "misconceptions": []}}
    }
    assert not grade(spec, {}, fast_but_broken).correct

    correct_and_quick = {
        "tools": {"score": {"delivered_intact": True, "efficiency": 0.9, "misconceptions": []}}
    }
    assert grade(spec, {}, correct_and_quick).correct

    correct_but_wasteful = {
        "tools": {
            "score": {
                "delivered_intact": True,
                "efficiency": 0.2,
                "misconceptions": ["gbn_vs_sr_confusion"],
            }
        }
    }
    result = grade(spec, {}, correct_but_wasteful)
    assert not result.correct
    assert "gbn_vs_sr_confusion" in result.misconceptions


def test_unknown_grader_kind_is_reported_not_crashed():
    result = grade({"kind": "does-not-exist"}, {})
    assert not result.correct
    assert result.detail["error"] == "unknown_grader"
