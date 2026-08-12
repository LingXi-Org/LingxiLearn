"""Deterministic grading.

Correctness is computed, never judged by a language model.  That is the whole
difference between "听起来对" and "对": the attribution grader checks the
learner's numbers against a waterfall our own parser derived from the capture,
and checks that every frame they cited actually plays the role they claimed.

Misconceptions fall out of *how* an answer is wrong — which bucket absorbed the
mass, which protocol event a decision ignored — not from asking a model to
speculate about the learner's mind.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from .contracts import Judgement

GraderFn = Callable[[dict[str, Any], Any, dict[str, Any]], Judgement]

_GRADERS: dict[str, GraderFn] = {}


def grader(kind: str) -> Callable[[GraderFn], GraderFn]:
    def register(fn: GraderFn) -> GraderFn:
        _GRADERS[kind] = fn
        return fn

    return register


def grade(
    spec: dict[str, Any],
    answer: Any,
    context: dict[str, Any] | None = None,
) -> Judgement:
    kind = str(spec.get("kind", ""))
    fn = _GRADERS.get(kind)
    if fn is None:
        return Judgement(
            correct=False,
            score=0.0,
            feedback=f"未知的判定方式：{kind}",
            detail={"error": "unknown_grader", "kind": kind},
        )
    return fn(spec, answer, context or {})


def _concept_scores(spec: dict[str, Any], score: float) -> dict[str, float]:
    concepts = spec.get("concepts") or []
    return {str(c): score for c in concepts}


def _as_text(answer: Any) -> str:
    if isinstance(answer, dict):
        return str(answer.get("text") or answer.get("value") or "")
    return str(answer or "")


# --------------------------------------------------------------------------
# Single / multiple choice
# --------------------------------------------------------------------------


@grader("choice")
def _choice(spec: dict[str, Any], answer: Any, _ctx: dict[str, Any]) -> Judgement:
    picked = answer.get("choice") if isinstance(answer, dict) else answer
    picked = str(picked or "").strip()
    expected = str(spec.get("answer", "")).strip()
    correct = bool(picked) and picked == expected
    score = 1.0 if correct else 0.0
    tags = []
    if not correct:
        tag = (spec.get("misconceptions") or {}).get(picked)
        if tag:
            tags.append(str(tag))
    return Judgement(
        correct=correct,
        score=score,
        concept_scores=_concept_scores(spec, score),
        misconceptions=tags,
        feedback=spec.get("feedback_correct", "") if correct else "",
        detail={"picked": picked},
    )


@grader("multi_choice")
def _multi_choice(spec: dict[str, Any], answer: Any, _ctx: dict[str, Any]) -> Judgement:
    picked = set(answer.get("choices", []) if isinstance(answer, dict) else (answer or []))
    expected = set(spec.get("answer", []))
    correct = picked == expected
    if expected:
        overlap = len(picked & expected)
        penalty = len(picked - expected)
        score = max(0.0, (overlap - penalty) / len(expected))
    else:
        score = 0.0
    tags = [
        str(tag)
        for opt, tag in (spec.get("misconceptions") or {}).items()
        if opt in (picked - expected)
    ]
    return Judgement(
        correct=correct,
        score=1.0 if correct else score,
        concept_scores=_concept_scores(spec, 1.0 if correct else score),
        misconceptions=tags,
        detail={"picked": sorted(picked), "expected": sorted(expected)},
    )


# --------------------------------------------------------------------------
# Numeric
# --------------------------------------------------------------------------


@grader("numeric")
def _numeric(spec: dict[str, Any], answer: Any, _ctx: dict[str, Any]) -> Judgement:
    raw = answer.get("value") if isinstance(answer, dict) else answer
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        return Judgement(
            correct=False, score=0.0, feedback="请给出一个数值。", detail={"raw": raw}
        )
    target = float(spec.get("value", 0.0))
    tolerance = float(spec.get("tolerance", max(abs(target) * 0.05, 1e-9)))
    correct = abs(value - target) <= tolerance
    score = 1.0 if correct else 0.0
    tags: list[str] = []
    for rule in spec.get("near_misses", []):
        if abs(value - float(rule["value"])) <= float(rule.get("tolerance", tolerance)):
            tags.append(str(rule["misconception"]))
    return Judgement(
        correct=correct,
        score=score,
        concept_scores=_concept_scores(spec, score),
        misconceptions=tags,
        detail={"value": value, "target": target, "tolerance": tolerance},
    )


# --------------------------------------------------------------------------
# Keyword rubric (deterministic text grading)
# --------------------------------------------------------------------------


@grader("keywords")
def _keywords(spec: dict[str, Any], answer: Any, _ctx: dict[str, Any]) -> Judgement:
    text = _as_text(answer)
    folded = re.sub(r"\s+", "", text).casefold()
    required: list[list[str]] = [
        [str(v) for v in (group if isinstance(group, list) else [group])]
        for group in spec.get("required", [])
    ]
    hits = sum(
        1 for group in required if any(re.sub(r"\s+", "", a).casefold() in folded for a in group)
    )


@grader("sim_outcome")
def _sim_outcome(spec: dict[str, Any], _answer: Any, ctx: dict[str, Any]) -> Judgement:
    """Grade a simulator delivery only after the artifact is intact."""

    outcome = _lookup(ctx, str(spec.get("score_from", "score")))
    if not isinstance(outcome, dict):
        return Judgement(
            correct=False,
            score=0.0,
            feedback="缺少模拟器结果，无法判定。",
            detail={"error": "missing_outcome"},
        )
    intact = bool(outcome.get("delivered_intact"))
    efficiency = float(outcome.get("efficiency", 0.0) or 0.0)
    minimum = float(spec.get("min_efficiency", 0.0) or 0.0)
    correct = intact and efficiency >= minimum
    score = efficiency if intact else 0.0
    return Judgement(
        correct=correct,
        score=score,
        concept_scores=_concept_scores(spec, score),
        misconceptions=[str(item) for item in outcome.get("misconceptions", [])],
        feedback="交付完整且效率达标。" if correct else "先保证交付结果完整，再优化效率。",
        detail={"delivered_intact": intact, "efficiency": efficiency, "min_efficiency": minimum},
    )
    score = hits / len(required) if required else 0.0
    threshold = float(spec.get("threshold", 0.75))
    tags = [
        str(tag)
        for phrase, tag in (spec.get("misconceptions") or {}).items()
        if re.sub(r"\s+", "", str(phrase)).casefold() in folded
    ]
    return Judgement(
        correct=score >= threshold,
        score=score,
        concept_scores=_concept_scores(spec, score),
        misconceptions=tags,
        detail={"matched": hits, "of": len(required), "threshold": threshold},
    )


# --------------------------------------------------------------------------
# Latency attribution — mission "慢在哪一环"
# --------------------------------------------------------------------------


@grader("attribution")
def _attribution(spec: dict[str, Any], answer: Any, ctx: dict[str, Any]) -> Judgement:
    """Grade a latency budget against ground truth computed from the capture.

    Two independent checks, both machine-verifiable:

    1. **Allocation** — does each bucket's share match what the packets say?
    2. **Citation** — is every pinned frame real, and does it actually play the
       role the learner assigned it to?  A right number backed by the wrong
       frame is not understanding, and this is where a chat window has nothing
       to offer: the frame roles are derived, not recalled.
    """
    truth = _lookup(ctx, spec.get("truth_from", "waterfall"))
    if not isinstance(truth, dict) or "buckets" not in truth:
        return Judgement(
            correct=False,
            score=0.0,
            feedback="缺少归因基准数据，无法判定。",
            detail={"error": "missing_truth"},
        )

    truth_buckets: dict[str, float] = {k: float(v) for k, v in truth["buckets"].items()}
    bucket_frames: dict[str, list[int]] = {
        k: [int(f) for f in v] for k, v in (truth.get("bucket_frames") or {}).items()
    }
    total = float(truth.get("total_ms") or sum(truth_buckets.values())) or 1.0

    payload = answer if isinstance(answer, dict) else {}
    allocations = {str(k): float(v) for k, v in (payload.get("allocations") or {}).items()}
    pins = {str(k): [int(f) for f in v] for k, v in (payload.get("pins") or {}).items()}

    # Accept either milliseconds or percentages.
    if allocations and sum(allocations.values()) <= 100.5 and total > 120:
        allocations = {k: v / 100.0 * total for k, v in allocations.items()}

    tol_ratio = float(spec.get("tolerance_ratio", 0.12))
    tol_floor = float(spec.get("tolerance_floor_ms", 8.0))
    require_pins = bool(spec.get("require_pins", True))

    per_bucket: dict[str, dict[str, Any]] = {}
    correct_buckets = 0
    for bucket, truth_ms in truth_buckets.items():
        claimed = allocations.get(bucket, 0.0)
        tolerance = max(tol_floor, tol_ratio * total)
        within = abs(claimed - truth_ms) <= tolerance

        valid_frames = set(bucket_frames.get(bucket, []))
        pinned = pins.get(bucket, [])
        good_pins = [f for f in pinned if f in valid_frames]
        bad_pins = [f for f in pinned if f not in valid_frames]
        pin_ok = (not require_pins) or (bool(good_pins) and not bad_pins)

        if within and pin_ok:
            correct_buckets += 1
        per_bucket[bucket] = {
            "claimed_ms": round(claimed, 2),
            "truth_ms": round(truth_ms, 2),
            "delta_ms": round(claimed - truth_ms, 2),
            "within_tolerance": within,
            "pins": pinned,
            "valid_pins": good_pins,
            "invalid_pins": bad_pins,
            "pin_ok": pin_ok,
        }

    score = correct_buckets / len(truth_buckets) if truth_buckets else 0.0
    threshold = float(spec.get("threshold", 0.8))

    # A citation that does not support its claim is a gate, not a deduction.
    # Otherwise, with five buckets, one bogus frame costs 0.2 and still passes —
    # which would teach exactly the habit this mission exists to break.
    bad_citations = [b for b, d in per_bucket.items() if d["invalid_pins"] or not d["pin_ok"]]
    passed = score >= threshold and not bad_citations

    tags = _attribution_misconceptions(spec, per_bucket, total)
    feedback = ""
    if passed:
        feedback = "归因与抓包数据一致，而且每个桶都有真实帧支撑。"
    elif bad_citations and score >= threshold:
        feedback = "数字对得上，但有的桶钉错了帧——结论的分量来自证据本身。"

    return Judgement(
        correct=passed,
        score=round(score, 4),
        concept_scores=_concept_scores(spec, score),
        misconceptions=tags,
        feedback=feedback,
        detail={
            "buckets": per_bucket,
            "total_ms": round(total, 2),
            "bad_citations": bad_citations,
        },
    )


def _attribution_misconceptions(
    spec: dict[str, Any], per_bucket: dict[str, dict[str, Any]], total: float
) -> list[str]:
    """Infer the misconception from which bucket absorbed the misplaced time."""
    tags: list[str] = []
    shift = float(spec.get("confusion_threshold_ratio", 0.1)) * total

    over = {b: d["delta_ms"] for b, d in per_bucket.items() if d["delta_ms"] >= shift}
    under = {b: -d["delta_ms"] for b, d in per_bucket.items() if d["delta_ms"] <= -shift}

    for rule in spec.get("confusions", []):
        src, dst, tag = rule.get("over"), rule.get("under"), str(rule.get("misconception", ""))
        if tag and src in over and dst in under:
            tags.append(tag)

    for bucket, detail in per_bucket.items():
        if detail["invalid_pins"]:
            pin_tag = (spec.get("pin_misconceptions") or {}).get(bucket)
            if pin_tag and str(pin_tag) not in tags:
                tags.append(str(pin_tag))
    return tags


def _lookup(ctx: dict[str, Any], key: str | None) -> Any:
    if not key:
        return None
    tools = ctx.get("tools") or {}
    return tools.get(key)
