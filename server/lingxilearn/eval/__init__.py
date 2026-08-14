"""Offline evaluation of the runtime.

The metric is learning gain, not satisfaction. A learner can enjoy a session
that taught them nothing, and optimising for how a turn felt is how a tutor
becomes a chat companion.
"""

from __future__ import annotations

from .learning_gain import (
    GainReport,
    evaluate_task,
    mastery_gain,
    misconception_resolution,
    prerequisite_closure,
)

__all__ = [
    "GainReport",
    "evaluate_task",
    "mastery_gain",
    "misconception_resolution",
    "prerequisite_closure",
]
