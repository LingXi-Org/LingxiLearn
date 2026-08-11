"""The answer-leakage guard is a product promise, so it gets real tests."""

from __future__ import annotations

from lingxilearn.kernel.policy import (
    LeakGuard,
    check_leakage,
    fallback_hint,
    next_hint_level,
    should_unlock_answer,
)

GUARD = LeakGuard(phrases=["重传停顿最大"], numbers=[225.8, 121.4])


def test_clean_hint_passes():
    verdict = check_leakage("先看看第 8 帧和第 9 帧的序号。", GUARD, answer_unlocked=False)
    assert not verdict.leaked


def test_phrase_leak_is_caught():
    verdict = check_leakage("其实重传停顿最大。", GUARD, answer_unlocked=False)
    assert verdict.leaked


def test_leak_survives_punctuation_and_spacing():
    """No word boundaries in Chinese, so folding must be by character, not token."""
    verdict = check_leakage("其实，重传 停顿、最大！", GUARD, answer_unlocked=False)
    assert verdict.leaked


def test_leak_survives_fullwidth_forms():
    verdict = check_leakage("重传停顿最大", GUARD, answer_unlocked=False)
    assert verdict.leaked


def test_numeric_leak_is_caught_within_tolerance():
    # 226 is close enough to 225.8 to give the answer away.
    assert check_leakage("大约 226 毫秒。", GUARD, answer_unlocked=False).leaked


def test_unrelated_number_is_not_a_leak():
    assert not check_leakage("看第 12 帧。", GUARD, answer_unlocked=False).leaked


def test_unlocking_permits_the_walkthrough():
    verdict = check_leakage("重传停顿最大，约 225.8 毫秒。", GUARD, answer_unlocked=True)
    assert not verdict.leaked


def test_hint_level_escalates_and_caps():
    assert next_hint_level(attempts=0, current=0) == 0
    assert next_hint_level(attempts=1, current=0) == 1
    assert next_hint_level(attempts=9, current=3) == 3


def test_answer_unlocks_only_on_request_after_effort():
    step = {"reveal_after": 3}
    assert not should_unlock_answer(attempts=5, step=step, learner_requested=False)
    assert not should_unlock_answer(attempts=1, step=step, learner_requested=True)
    assert should_unlock_answer(attempts=3, step=step, learner_requested=True)


def test_fallback_hint_walks_the_authored_ladder():
    step = {"hint_ladder": ["一级", "二级", "三级"]}
    assert fallback_hint(step, 0) == "一级"
    assert fallback_hint(step, 2) == "三级"
    assert fallback_hint(step, 9) == "三级"  # clamps rather than crashing
    assert fallback_hint({}, 0)  # always returns something usable
