"""Evaluate a :class:`DoneCondition` against the world.

The point of this module is a single rule: **a provider returning is not a task
completing.**  A deck agent can finish its turn without a valid deck; a teaching
turn can happen without producing any evidence.  Every planned task states what
must be true afterwards, and this is where that statement is checked.

When a condition does not hold, the loop replans instead of moving on — which is
how a step's outcome changes what the next step will be.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from .contracts import DoneCondition


class ArtifactProbe(Protocol):
    """What completion needs from the artifact store, and nothing more."""

    def exists(self, artifact: str) -> bool: ...

    def is_valid(self, artifact: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class CompletionContext:
    """The facts a done-condition may be evaluated against."""

    artifacts: ArtifactProbe | None = None
    evidence: Sequence[Mapping[str, Any]] = ()
    """Evidence appended during this task, not the learner's whole history."""
    profile: Mapping[str, Mapping[str, Any]] = None  # type: ignore[assignment]
    """Current profile rows keyed by knowledge_point_id."""
    user_replied: bool = False
    quiz_graded: bool = False
    provider_result: bool = False
    """The provider returned a successful, host-observed result for this task."""

    def __post_init__(self) -> None:
        if self.profile is None:
            object.__setattr__(self, "profile", {})


@dataclass(frozen=True, slots=True)
class Verdict:
    """Whether the condition held, and a sentence explaining the answer."""

    satisfied: bool
    detail: str

    def __bool__(self) -> bool:
        return self.satisfied


def evaluate(condition: DoneCondition | None, context: CompletionContext) -> Verdict:
    """Check one condition. Unknown kinds fail closed rather than passing."""

    if condition is None:
        return Verdict(True, "未声明完成条件，按执行即完成处理")

    match condition.kind:
        case "always":
            return Verdict(True, "执行即完成")

        case "artifact_exists":
            if context.artifacts is None:
                return Verdict(False, "无法访问产物存储")
            ok = context.artifacts.exists(condition.artifact)
            return Verdict(ok, f"产物 {condition.artifact} " + ("已存在" if ok else "不存在"))

        case "artifact_valid":
            if context.artifacts is None:
                return Verdict(False, "无法访问产物存储")
            if not context.artifacts.exists(condition.artifact):
                return Verdict(False, f"产物 {condition.artifact} 不存在")
            ok = context.artifacts.is_valid(condition.artifact)
            return Verdict(ok, f"产物 {condition.artifact} " + ("通过校验" if ok else "未通过校验"))

        case "evidence_observed":
            matched = [
                row
                for row in context.evidence
                if str(row.get("signal") or "") == condition.signal
                and (
                    not condition.knowledge_point_id
                    or str(row.get("knowledge_point") or "") == condition.knowledge_point_id
                )
            ]
            ok = len(matched) >= condition.min_count
            return Verdict(
                ok,
                f"观察到 {len(matched)}/{condition.min_count} 条 {condition.signal} 证据",
            )

        case "provider_result":
            return Verdict(
                context.provider_result,
                "执行者已产生有效结果" if context.provider_result else "执行者尚未产生有效结果",
            )

        case "profile_reaches":
            row = context.profile.get(condition.knowledge_point_id)
            if row is None:
                return Verdict(False, f"{condition.knowledge_point_id} 尚无档案记录")
            mastery = float(row.get("mastery") or 0.0)
            ok = mastery >= condition.mastery
            return Verdict(
                ok,
                f"{condition.knowledge_point_id} 掌握度 {mastery:.2f}，"
                f"目标 {condition.mastery:.2f}",
            )

        case "user_replied":
            return Verdict(
                context.user_replied, "学习者已回复" if context.user_replied else "仍在等待学习者"
            )

        case "quiz_graded":
            return Verdict(
                context.quiz_graded, "测评已判分" if context.quiz_graded else "测评尚未判分"
            )

        case "all_of":
            verdicts = [evaluate(item, context) for item in condition.conditions]
            failed = [v for v in verdicts if not v.satisfied]
            if failed:
                return Verdict(False, "未全部满足：" + "；".join(v.detail for v in failed))
            return Verdict(True, "全部条件已满足")

        case "any_of":
            verdicts = [evaluate(item, context) for item in condition.conditions]
            passed = next((v for v in verdicts if v.satisfied), None)
            if passed is not None:
                return Verdict(True, passed.detail)
            return Verdict(False, "无一满足：" + "；".join(v.detail for v in verdicts))

    # Fail closed: an unrecognised kind must not silently mark work complete.
    return Verdict(False, f"未知的完成条件类型：{condition.kind}")


class StoreArtifactProbe:
    """Adapts :class:`~lingxilearn.agents.artifact_store.ArtifactStore` to the protocol."""

    _PATHS = {
        "lesson-intro": "lesson_intro_path",
        "lecture-deck": "deck_path",
        "visual": "html_path",
    }

    def __init__(self, store: Any, task_id: str, *, validations: dict[str, bool] | None = None):
        self._store = store
        self._task_id = task_id
        self._validations = dict(validations or {})

    def exists(self, artifact: str) -> bool:
        accessor = self._PATHS.get(artifact)
        if accessor is None:
            return False
        path_of = getattr(self._store, accessor, None)
        if not callable(path_of):
            return False
        try:
            return bool(path_of(self._task_id).exists())
        except Exception:  # noqa: BLE001 - a missing artifact is not an error here
            return False

    def is_valid(self, artifact: str) -> bool:
        """Validation results are recorded by the provider that produced the artifact.

        Re-running a validator here would mean re-building a deck inside a
        predicate check, so the producing step records its verdict and this
        reads it. An artifact with no recorded verdict is not assumed valid.
        """

        return bool(self._validations.get(artifact, False))

    def record(self, artifact: str, valid: bool) -> None:
        self._validations[artifact] = bool(valid)


__all__ = [
    "ArtifactProbe",
    "CompletionContext",
    "StoreArtifactProbe",
    "Verdict",
    "evaluate",
]
