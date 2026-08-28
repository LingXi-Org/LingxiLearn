"""Teaching policy: the hint ladder and the answer-leakage guard.

The product promise is "引导、提示、验证，而不是代做".  A system prompt asking a
model to please not give the answer is not a mechanism.  This module makes it
one: the hint level is program state the kernel owns, and every coaching turn
is post-validated against the step's answer markers before the learner sees it.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

MAX_HINT_LEVEL = 3
"""H0 pure question · H1 point at the evidence · H2 concept scaffold · H3 partial reasoning."""


@dataclass(frozen=True, slots=True)
class LeakGuard:
    """What counts as giving the answer away for one step."""

    phrases: list[str] = field(default_factory=list)
    """Text that constitutes the answer, e.g. "DNS 解析占了大头"."""
    numbers: list[float] = field(default_factory=list)
    """Values that give it away, e.g. the 121 ms gap the learner must find."""
    number_tolerance: float = 0.02
    """Relative tolerance when matching a number in the text."""

    @classmethod
    def from_step(cls, step: dict[str, Any]) -> LeakGuard:
        guard = step.get("leak_guard") or {}
        return cls(
            phrases=[str(p) for p in guard.get("phrases", [])],
            numbers=[float(n) for n in guard.get("numbers", [])],
            number_tolerance=float(guard.get("number_tolerance", 0.02)),
        )


@dataclass(frozen=True, slots=True)
class LeakVerdict:
    leaked: bool
    reasons: list[str] = field(default_factory=list)


_PUNCT = re.compile(r"[\s　,.;:!?，。；：！？、\-_/()（）\[\]【】\"'“”‘’]+")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).casefold()
    return _PUNCT.sub("", folded)


def check_leakage(text: str, guard: LeakGuard, *, answer_unlocked: bool) -> LeakVerdict:
    """Decide whether ``text`` may be shown to the learner right now.

    Punctuation and full/half-width differences are folded away first, so a
    model cannot slip an answer through by rephrasing spacing — this matters
    for Chinese text, where there are no word boundaries to anchor on.
    """
    if answer_unlocked:
        return LeakVerdict(leaked=False)

    reasons: list[str] = []
    haystack = _normalize(text)
    for phrase in guard.phrases:
        needle = _normalize(phrase)
        if needle and needle in haystack:
            reasons.append(f"phrase:{phrase}")

    if guard.numbers:
        found = [float(m) for m in _NUMBER.findall(unicodedata.normalize("NFKC", text))]
        for target in guard.numbers:
            scale = max(abs(target), 1.0) * guard.number_tolerance
            if any(abs(value - target) <= scale for value in found):
                reasons.append(f"number:{target}")

    return LeakVerdict(leaked=bool(reasons), reasons=reasons)


def next_hint_level(*, attempts: int, current: int, max_level: int = MAX_HINT_LEVEL) -> int:
    """Escalate one rung per failed attempt, never past the ceiling."""
    return min(max(current, 0) + 1, max_level) if attempts > 0 else max(current, 0)


def should_unlock_answer(*, attempts: int, step: dict[str, Any], learner_requested: bool) -> bool:
    """The answer opens only after real effort, and only if the learner asks.

    ``reveal_after`` defaults to 3 genuine attempts.  Reaching it is necessary
    but not sufficient — the learner still has to ask for the walkthrough, so
    the system never volunteers the answer to someone still working.
    """
    threshold = int(step.get("reveal_after", 3))
    return learner_requested and attempts >= threshold
