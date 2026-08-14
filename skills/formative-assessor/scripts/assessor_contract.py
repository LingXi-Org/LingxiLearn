#!/usr/bin/env python3
"""Validate formative-assessor task/result contracts and evidence boundaries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


TASK_VERSION = "formative-assessor-task.v1"
RESULT_VERSION = "formative-assessor-result.v1"
EVIDENCE_STATES = {"not_observed", "emerging", "demonstrated", "misconception_evidence", "needs_recheck"}
POLICY_SIGNALS = {
    "advance", "retrieve_or_predict", "minimal_cue", "progressive_hint", "conceptual_conflict",
    "worked_example_fade", "targeted_explanation", "teach_back", "transfer_check",
}
CONFIDENCE_SOURCES = {"learner_reported", "ui_captured", "not_provided"}
FORBIDDEN_RESULT_KEYS = {"student_response", "tutoring_message", "question_to_learner", "mandatory_action"}


class ContractError(ValueError):
    pass


def load(path: str) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"无法读取 JSON：{path}: {exc}") from exc


def require_object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{name} 必须是 JSON 对象")
    return value


def required(obj: dict[str, Any], keys: set[str], name: str) -> None:
    missing = keys - obj.keys()
    if missing:
        raise ContractError(f"{name} 缺少字段：{sorted(missing)}")


def string_list(value: Any, name: str, min_items: int = 0) -> list[str]:
    if not isinstance(value, list) or len(value) < min_items or not all(isinstance(x, str) and x for x in value):
        raise ContractError(f"{name} 必须是至少 {min_items} 个非空字符串的数组")
    return value


def validate_task(obj: Any) -> None:
    task = require_object(obj, "task")
    required(task, {"schema_version", "task_id", "concept", "grader_evidence"}, "task")
    if task["schema_version"] != TASK_VERSION:
        raise ContractError(f"task.schema_version 必须为 {TASK_VERSION}")
    for key in ("task_id", "concept"):
        if not isinstance(task[key], str) or not task[key]:
            raise ContractError(f"task.{key} 必须是非空字符串")
    evidence = require_object(task["grader_evidence"], "task.grader_evidence")
    required(evidence, {"correctness", "independent", "evidence_refs"}, "grader_evidence")
    if evidence["correctness"] not in {"correct", "incorrect", "partial", "ambiguous", "ungraded"}:
        raise ContractError("grader_evidence.correctness 无效")
    if not isinstance(evidence["independent"], bool):
        raise ContractError("grader_evidence.independent 必须是布尔值")
    string_list(evidence["evidence_refs"], "grader_evidence.evidence_refs", 1)
    if evidence.get("confidence_source") not in CONFIDENCE_SOURCES:
        raise ContractError("grader_evidence.confidence_source 必须明确为 learner_reported/ui_captured/not_provided")
    confidence = evidence.get("confidence")
    if confidence not in {"high", "medium", "low", None}:
        raise ContractError("grader_evidence.confidence 无效")
    if evidence.get("confidence_source") == "not_provided" and confidence is not None:
        raise ContractError("confidence_source=not_provided 时 confidence 必须为 null")
    if confidence is not None and evidence.get("confidence_source") == "not_provided":
        raise ContractError("不得从未提供的信号推断 confidence")


def validate_result(obj: Any) -> None:
    result = require_object(obj, "result")
    required(result, {
        "schema_version", "task_id", "concept", "evidence_state", "independent", "confidence",
        "next_probe_needed", "recommended_policy_signal", "evidence_refs", "rationale", "limitations",
    }, "result")
    if result["schema_version"] != RESULT_VERSION:
        raise ContractError(f"result.schema_version 必须为 {RESULT_VERSION}")
    for key in ("task_id", "concept", "rationale"):
        if not isinstance(result[key], str) or not result[key]:
            raise ContractError(f"result.{key} 必须是非空字符串")
    if result["evidence_state"] not in EVIDENCE_STATES:
        raise ContractError("result.evidence_state 无效")
    if not isinstance(result["independent"], bool) or not isinstance(result["next_probe_needed"], bool):
        raise ContractError("result.independent 和 next_probe_needed 必须是布尔值")
    if result["confidence"] not in {"high", "medium", "low", None}:
        raise ContractError("result.confidence 无效")
    if result.get("confidence_basis") not in CONFIDENCE_SOURCES:
        raise ContractError("result.confidence_basis 无效")
    if result["confidence_basis"] == "not_provided" and result["confidence"] is not None:
        raise ContractError("confidence_basis=not_provided 时 confidence 必须为 null")
    if result["recommended_policy_signal"] not in POLICY_SIGNALS:
        raise ContractError("result.recommended_policy_signal 无效")
    string_list(result["evidence_refs"], "result.evidence_refs", 1)
    if not isinstance(result["limitations"], list) or not all(isinstance(x, str) for x in result["limitations"]):
        raise ContractError("result.limitations 必须是字符串数组")
    if result["next_probe_needed"] and not isinstance(result.get("probe_reason"), str):
        raise ContractError("next_probe_needed=true 时必须提供 probe_reason")
    if result["evidence_state"] == "misconception_evidence" and not isinstance(result.get("error_pattern"), str):
        raise ContractError("misconception_evidence 必须提供 error_pattern")
    forbidden = FORBIDDEN_RESULT_KEYS & result.keys()
    if forbidden:
        raise ContractError(f"结果不得包含 learner-facing 字段：{sorted(forbidden)}")


def validate_pair(task_obj: Any, result_obj: Any) -> None:
    validate_task(task_obj)
    validate_result(result_obj)
    task = task_obj
    result = result_obj
    if task["task_id"] != result["task_id"] or task["concept"] != result["concept"]:
        raise ContractError("task_id 或 concept 与 result 不一致")
    allowed_refs = set(task["grader_evidence"]["evidence_refs"])
    result_refs = set(result["evidence_refs"])
    if not result_refs.issubset(allowed_refs):
        raise ContractError("result.evidence_refs 含输入中不存在的证据 ID")
    if result["independent"] != task["grader_evidence"]["independent"]:
        raise ContractError("result.independent 必须复制确定性输入证据")
    source = task["grader_evidence"].get("confidence_source")
    if result["confidence_basis"] != source:
        raise ContractError("result.confidence_basis 必须复制输入 confidence_source")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    task_cmd = sub.add_parser("validate-task")
    task_cmd.add_argument("task")
    result_cmd = sub.add_parser("validate-result")
    result_cmd.add_argument("result")
    pair_cmd = sub.add_parser("validate-pair")
    pair_cmd.add_argument("task")
    pair_cmd.add_argument("result")
    args = parser.parse_args()
    try:
        if args.command == "validate-task":
            validate_task(load(args.task))
            print(f"校验通过：{TASK_VERSION}")
        elif args.command == "validate-result":
            validate_result(load(args.result))
            print(f"校验通过：{RESULT_VERSION}")
        else:
            validate_pair(load(args.task), load(args.result))
            print("校验通过：formative-assessor task/result pair")
        return 0
    except ContractError as exc:
        print(f"校验失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
