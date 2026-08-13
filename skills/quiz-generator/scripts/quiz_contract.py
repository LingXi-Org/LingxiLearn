#!/usr/bin/env python3
"""Validate quiz-generator contracts and create a grading-safe public snapshot."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

QUESTION_ID_RE = re.compile(r"^q[0-9A-Za-z_-]+$")
QUESTION_TYPES = {"single_choice", "multi_choice", "short_text"}


class ContractError(ValueError):
    pass


def _load(path: str) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ContractError("root value must be a JSON object")
    return value


def _require_keys(obj: dict[str, Any], required: set[str], allowed: set[str], where: str) -> None:
    missing = required - obj.keys()
    extra = obj.keys() - allowed
    if missing:
        raise ContractError(f"{where}: missing required keys: {sorted(missing)}")
    if extra:
        raise ContractError(f"{where}: unexpected keys: {sorted(extra)}")


def validate_input(obj: dict[str, Any]) -> None:
    required = {"schema_version", "task_id", "intent", "interactive_lecture_deck"}
    allowed = required | {"lesson_intro"}
    _require_keys(obj, required, allowed, "input")
    if obj["schema_version"] != "quiz-generation-input.v2":
        raise ContractError("input.schema_version must be quiz-generation-input.v2")
    if not isinstance(obj["task_id"], str) or not obj["task_id"]:
        raise ContractError("input.task_id must be a non-empty string")
    if not isinstance(obj["intent"], dict):
        raise ContractError("input.intent must be an object")
    if not isinstance(obj["interactive_lecture_deck"], dict) or obj["interactive_lecture_deck"].get("schema_version") != "interactive-lecture-deck-result.v2":
        raise ContractError("input.interactive_lecture_deck.schema_version must be interactive-lecture-deck-result.v2")
    if "lesson_intro" in obj and not isinstance(obj["lesson_intro"], (str, dict)):
        raise ContractError("input.lesson_intro must be HTML text or an object")


def _validate_option(option: Any, qid: str, index: int) -> None:
    if not isinstance(option, dict):
        raise ContractError(f"{qid}.options[{index}] must be an object")
    _require_keys(option, {"id", "label"}, {"id", "label"}, f"{qid}.options[{index}]")
    if not isinstance(option["id"], str) or not option["id"]:
        raise ContractError(f"{qid}.options[{index}].id must be a non-empty string")
    if not isinstance(option["label"], str) or not option["label"]:
        raise ContractError(f"{qid}.options[{index}].label must be a non-empty string")


def validate_result(obj: dict[str, Any]) -> None:
    required = {"schema_version", "task_id", "title", "instructions", "questions", "total_points"}
    _require_keys(obj, required, required | {"assumptions"}, "result")
    if obj["schema_version"] != "quiz-generation-result.v1":
        raise ContractError("result.schema_version must be quiz-generation-result.v1")
    for key in ("task_id", "title", "instructions"):
        if not isinstance(obj[key], str) or not obj[key]:
            raise ContractError(f"result.{key} must be a non-empty string")
    if not isinstance(obj["questions"], list) or not 1 <= len(obj["questions"]) <= 20:
        raise ContractError("result.questions must contain 1..20 questions")
    if not isinstance(obj["total_points"], int) or obj["total_points"] < 1:
        raise ContractError("result.total_points must be an integer >= 1")
    if "assumptions" in obj and (not isinstance(obj["assumptions"], list) or not all(isinstance(x, str) for x in obj["assumptions"])):
        raise ContractError("result.assumptions must be an array of strings")

    seen_ids: set[str] = set()
    point_sum = 0
    for index, question in enumerate(obj["questions"]):
        where = f"questions[{index}]"
        if not isinstance(question, dict):
            raise ContractError(f"{where} must be an object")
        required_question = {"id", "type", "prompt", "options", "points", "answer", "explanation", "keywords"}
        _require_keys(question, required_question, required_question, where)
        qid = question["id"]
        if not isinstance(qid, str) or not QUESTION_ID_RE.fullmatch(qid):
            raise ContractError(f"{where}.id is invalid: {qid!r}")
        if qid in seen_ids:
            raise ContractError(f"duplicate question id: {qid}")
        seen_ids.add(qid)
        if question["type"] not in QUESTION_TYPES:
            raise ContractError(f"{qid}.type is invalid")
        if not isinstance(question["prompt"], str) or not question["prompt"]:
            raise ContractError(f"{qid}.prompt must be a non-empty string")
        if not isinstance(question["options"], list) or len(question["options"]) > 8:
            raise ContractError(f"{qid}.options must be an array with <= 8 items")
        for option_index, option in enumerate(question["options"]):
            _validate_option(option, qid, option_index)
        if question["type"] in {"single_choice", "multi_choice"} and len(question["options"]) < 2:
            raise ContractError(f"{qid}: choice questions need at least 2 options")
        if question["type"] == "short_text" and question["options"]:
            raise ContractError(f"{qid}: short_text options should be empty")
        if not isinstance(question["points"], int) or not 1 <= question["points"] <= 100:
            raise ContractError(f"{qid}.points must be an integer from 1 to 100")
        if not isinstance(question["explanation"], str):
            raise ContractError(f"{qid}.explanation must be a string")
        if not isinstance(question["keywords"], list) or len(question["keywords"]) > 20 or not all(isinstance(x, str) for x in question["keywords"]):
            raise ContractError(f"{qid}.keywords must be an array of <=20 strings")
        point_sum += question["points"]
    if point_sum != obj["total_points"]:
        raise ContractError(f"total_points={obj['total_points']} but question points sum to {point_sum}")


def sanitize_public(obj: dict[str, Any]) -> dict[str, Any]:
    validate_result(obj)
    return {
        "schema_version": obj["schema_version"],
        "task_id": obj["task_id"],
        "title": obj["title"],
        "instructions": obj["instructions"],
        "questions": [
            {key: question[key] for key in ("id", "type", "prompt", "options", "points")}
            for question in obj["questions"]
        ],
        "total_points": obj["total_points"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    for command in ("validate-input", "validate-result", "sanitize"):
        subparser = sub.add_parser(command)
        subparser.add_argument("input")
        if command == "sanitize":
            subparser.add_argument("-o", "--output")
    args = parser.parse_args()
    try:
        obj = _load(args.input)
        if args.cmd == "validate-input":
            validate_input(obj)
            print("校验通过：quiz-generation-input.v2")
        elif args.cmd == "validate-result":
            validate_result(obj)
            print("校验通过：quiz-generation-result.v1")
        else:
            text = json.dumps(sanitize_public(obj), ensure_ascii=False, indent=2) + "\n"
            if args.output:
                Path(args.output).write_text(text, encoding="utf-8")
            else:
                sys.stdout.write(text)
        return 0
    except (OSError, json.JSONDecodeError, ContractError) as exc:
        print(f"校验失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
