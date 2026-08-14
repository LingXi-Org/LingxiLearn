#!/usr/bin/env python3
"""Validate retrieval-practice-builder task/result contracts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


TASK_VERSION = "retrieval-practice-builder-task.v1"
RESULT_VERSION = "retrieval-practice-builder-result.v1"
TARGET_TYPES = {"retrieval", "near_transfer", "far_transfer", "boundary_case", "misconception_discriminator"}
FORMATS = {"short_text", "single_choice", "multi_choice", "numeric", "classification", "prediction"}
PUBLIC_FORBIDDEN = {"answer", "grading_key", "explanation", "rubric", "keywords", "assumptions"}


class ContractError(ValueError):
    pass


def load(path: str) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"无法读取 JSON：{path}: {exc}") from exc


def obj(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{name} 必须是对象")
    return value


def req(value: dict[str, Any], keys: set[str], name: str) -> None:
    missing = keys - value.keys()
    if missing:
        raise ContractError(f"{name} 缺少字段：{sorted(missing)}")


def strings(value: Any, name: str, minimum: int = 0) -> list[str]:
    if not isinstance(value, list) or len(value) < minimum or not all(isinstance(x, str) and x for x in value):
        raise ContractError(f"{name} 必须是至少 {minimum} 个非空字符串的数组")
    return value


def validate_task(value: Any) -> None:
    task = obj(value, "task")
    req(task, {"schema_version", "task_id", "concept", "learning_objective", "target_type", "learner_evidence", "difficulty", "constraints"}, "task")
    if task["schema_version"] != TASK_VERSION:
        raise ContractError(f"task.schema_version 必须为 {TASK_VERSION}")
    for key in ("task_id", "concept", "learning_objective"):
        if not isinstance(task[key], str) or not task[key]:
            raise ContractError(f"task.{key} 必须是非空字符串")
    targets = task["target_type"]
    if not isinstance(targets, list) or not targets or not set(targets).issubset(TARGET_TYPES):
        raise ContractError("task.target_type 必须包含合法 target type")
    evidence = obj(task["learner_evidence"], "task.learner_evidence")
    strings(evidence.get("evidence_refs"), "learner_evidence.evidence_refs", 1)
    difficulty = task["difficulty"]
    level = difficulty.get("level") if isinstance(difficulty, dict) else difficulty
    if level not in {"easy", "medium", "hard"}:
        raise ContractError("task.difficulty.level 无效")
    constraints = obj(task["constraints"], "task.constraints")
    max_candidates = constraints.get("max_candidates")
    if not isinstance(max_candidates, int) or not 1 <= max_candidates <= 3:
        raise ContractError("constraints.max_candidates 必须为 1..3")
    if constraints.get("language") not in {None, "zh-CN"}:
        raise ContractError("constraints.language 必须为 zh-CN")


def validate_grading_key(value: Any, name: str) -> None:
    key = obj(value, name)
    req(key, {"answer", "rubric"}, name)
    if not isinstance(key["rubric"], str) or not key["rubric"]:
        raise ContractError(f"{name}.rubric 必须是非空字符串")
    if "keywords" in key:
        strings(key["keywords"], f"{name}.keywords")


def validate_candidate(value: Any, index: int, allowed_refs: set[str]) -> None:
    candidate = obj(value, f"candidates[{index}]")
    req(candidate, {"id", "target_type", "prompt", "response_format", "difficulty", "evidence_refs", "misconception_targets", "grading_key"}, f"candidates[{index}]")
    if not isinstance(candidate["id"], str) or not candidate["id"].startswith("rp"):
        raise ContractError(f"candidates[{index}].id 无效")
    if candidate["target_type"] not in TARGET_TYPES or candidate["response_format"] not in FORMATS:
        raise ContractError(f"candidates[{index}] 的 target_type 或 response_format 无效")
    if candidate["difficulty"] not in {"easy", "medium", "hard"}:
        raise ContractError(f"candidates[{index}].difficulty 无效")
    if not isinstance(candidate["prompt"], str) or not candidate["prompt"]:
        raise ContractError(f"candidates[{index}].prompt 必须是非空字符串")
    refs = set(strings(candidate["evidence_refs"], f"candidates[{index}].evidence_refs", 1))
    if not refs.issubset(allowed_refs):
        raise ContractError(f"candidates[{index}] 使用了输入外的 evidence_refs")
    strings(candidate["misconception_targets"], f"candidates[{index}].misconception_targets")
    validate_grading_key(candidate["grading_key"], f"candidates[{index}].grading_key")
    if candidate["response_format"] in {"single_choice", "multi_choice"}:
        options = candidate.get("options")
        if not isinstance(options, list) or len(options) < 2:
            raise ContractError(f"candidates[{index}] 选择题必须有至少两个 options")


def validate_public_task(value: Any) -> None:
    public = obj(value, "public_task")
    req(public, {"candidate_id", "target_type", "prompt", "response_format"}, "public_task")
    forbidden = PUBLIC_FORBIDDEN & public.keys()
    if forbidden:
        raise ContractError(f"public_task 不得包含内部字段：{sorted(forbidden)}")
    if public["target_type"] not in TARGET_TYPES or public["response_format"] not in FORMATS:
        raise ContractError("public_task 的 target_type 或 response_format 无效")
    if not isinstance(public["prompt"], str) or not public["prompt"]:
        raise ContractError("public_task.prompt 必须是非空字符串")


def validate_result(value: Any, task: dict[str, Any] | None = None) -> None:
    result = obj(value, "result")
    req(result, {"schema_version", "task_id", "status", "concept", "candidates", "selection", "public_task", "grading_key", "validation", "prefetch", "evidence_refs", "warnings"}, "result")
    if result["schema_version"] != RESULT_VERSION:
        raise ContractError(f"result.schema_version 必须为 {RESULT_VERSION}")
    if result["status"] not in {"ready", "insufficient_evidence", "discarded"}:
        raise ContractError("result.status 无效")
    for key in ("task_id", "concept"):
        if not isinstance(result[key], str) or not result[key]:
            raise ContractError(f"result.{key} 必须是非空字符串")
    refs = set(strings(result["evidence_refs"], "result.evidence_refs", 1))
    candidates = result["candidates"]
    if not isinstance(candidates, list) or len(candidates) > 3:
        raise ContractError("result.candidates 必须是 0..3 个候选任务")
    allowed_refs = set(task["learner_evidence"]["evidence_refs"]) if task else refs
    ids: set[str] = set()
    for index, candidate in enumerate(candidates):
        validate_candidate(candidate, index, allowed_refs)
        if candidate["id"] in ids:
            raise ContractError("candidate id 重复")
        ids.add(candidate["id"])
    validation = obj(result["validation"], "result.validation")
    req(validation, {"answerable", "evidence_grounded", "misconception_checked", "difficulty_checked", "public_internal_separated"}, "result.validation")
    for key in ("answerable", "evidence_grounded", "misconception_checked", "difficulty_checked", "public_internal_separated"):
        if not isinstance(validation[key], bool):
            raise ContractError(f"validation.{key} 必须是布尔值")
    prefetch = obj(result["prefetch"], "result.prefetch")
    req(prefetch, {"blocking", "discard_if", "cache_key"}, "result.prefetch")
    if prefetch["blocking"] is not False:
        raise ContractError("prefetch.blocking 必须为 false")
    strings(prefetch["discard_if"], "prefetch.discard_if", 1)
    if not isinstance(prefetch["cache_key"], str) or not prefetch["cache_key"]:
        raise ContractError("prefetch.cache_key 必须是非空字符串")
    strings(result["warnings"], "result.warnings")
    if result["status"] == "ready":
        if not candidates or not isinstance(result["selection"], dict):
            raise ContractError("ready 结果必须有 candidates 和 selection")
        selection = result["selection"]
        req(selection, {"candidate_id", "reason"}, "result.selection")
        if selection["candidate_id"] not in ids:
            raise ContractError("selection.candidate_id 不存在")
        validate_public_task(result["public_task"])
        validate_grading_key(result["grading_key"], "result.grading_key")
        if result["public_task"]["candidate_id"] != selection["candidate_id"]:
            raise ContractError("public_task.candidate_id 与 selection 不一致")
    else:
        if result["selection"] is not None or result["public_task"] is not None or result["grading_key"] is not None:
            raise ContractError("非 ready 结果不得提供 selection/public_task/grading_key")
    if task:
        if result["task_id"] != task["task_id"] or result["concept"] != task["concept"]:
            raise ContractError("result.task_id 或 concept 与 task 不一致")
        if not refs.issubset(allowed_refs):
            raise ContractError("result.evidence_refs 含输入外的 evidence ID")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate-task", "validate-result"):
        cmd = sub.add_parser(name)
        cmd.add_argument("path")
    pair = sub.add_parser("validate-pair")
    pair.add_argument("task")
    pair.add_argument("result")
    args = parser.parse_args()
    try:
        if args.command == "validate-task":
            validate_task(load(args.path))
            print(f"校验通过：{TASK_VERSION}")
        elif args.command == "validate-result":
            validate_result(load(args.path))
            print(f"校验通过：{RESULT_VERSION}")
        else:
            task = load(args.task)
            validate_task(task)
            validate_result(load(args.result), task)
            print("校验通过：retrieval-practice-builder task/result pair")
        return 0
    except ContractError as exc:
        print(f"校验失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
