"""Deterministic grading for generated quizzes.

Moved out of the service unchanged so the grading provider and the quiz-submission
endpoint share one implementation.  It is separate from
:mod:`lingxilearn.kernel.graders`, which grades authored course-pack items: those
carry a declared grader kind and answer markers, while a generated quiz carries
a question type and an answer key, and conflating the two shapes would mean
grading one of them badly.

No model is involved. A model's opinion about whether an answer is right is not
a grade, and mastery only moves on grades.
"""

from __future__ import annotations

from typing import Any

_RUBRIC_PREFIXES = ("concept:", "bloom:", "difficulty:", "purpose:")


def _expected_options(expected: Any) -> list[Any]:
    if isinstance(expected, dict):
        return list(expected.get("option_ids", []) or [])
    if isinstance(expected, list):
        return list(expected)
    return [expected] if expected is not None else []


def _rubric_keywords(question: dict[str, Any], expected: Any) -> list[str]:
    """The keywords that actually have to appear, minus the rubric annotations.

    Quiz authors tag questions with ``concept:``/``bloom:`` markers in the same
    list; treating those as required text would fail every correct answer.
    """

    declared = expected.get("keywords", []) if isinstance(expected, dict) else []
    return [
        str(item).strip().casefold()
        for item in (declared or question.get("keywords", []))
        if str(item).strip() and not str(item).startswith(_RUBRIC_PREFIXES)
    ]


def grade_quiz(quiz: dict[str, Any], answers: dict[str, Any]) -> dict[str, Any]:
    """Grade every question, returning per-question detail and the totals."""

    per_question: list[dict[str, Any]] = []
    total_score = 0.0
    total_points = 0

    for question in quiz.get("questions", []):
        qid = str(question.get("id", ""))
        points = int(question.get("points", 1))
        total_points += points
        actual = answers.get(qid)
        expected = question.get("answer")
        qtype = question.get("type")
        options = _expected_options(expected)

        if qtype == "multi_choice":
            correct = set(actual or []) == {str(item) for item in options} or set(
                actual or []
            ) == set(options)
        elif qtype == "short_text":
            text = str(actual or "").strip().casefold()
            keywords = _rubric_keywords(question, expected)
            correct = bool(keywords) and all(keyword in text for keyword in keywords)
        else:
            correct = str(actual or "") in {str(item) for item in options}

        answered = actual not in (None, "", [], {})
        score = points if correct else 0
        total_score += score
        per_question.append(
            {
                "id": qid,
                "correct": correct,
                "answered": answered,
                "score": score,
                "points": points,
                "misconceptions": _misconceptions_for(question, actual, correct),
            }
        )

    return {
        "per_question": per_question,
        "total_score": total_score,
        "total_points": total_points,
    }


def _misconceptions_for(question: dict[str, Any], actual: Any, correct: bool) -> list[str]:
    """Tags the question author attached to the specific wrong choice."""

    if correct:
        return []
    mapping = question.get("misconceptions")
    if not isinstance(mapping, dict):
        return []
    picked = actual if isinstance(actual, list) else [actual]
    return [str(mapping[key]) for key in (str(item) for item in picked) if key in mapping]


__all__ = ["grade_quiz"]
