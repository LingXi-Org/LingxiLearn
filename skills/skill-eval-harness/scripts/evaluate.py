#!/usr/bin/env python3
"""Deterministic evaluator for Lingxi teaching Skill run artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


RUN_VERSION = "skill-eval-run.v1"
REPORT_VERSION = "skill-eval-report.v1"
REQUIRED_METADATA = {
    "phase",
    "critical-path",
    "learner-facing",
    "state-write-mode",
    "parallel-safe",
    "latency-class",
    "eval-suite",
}


class EvalError(ValueError):
    pass


def load_json(path: str | Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvalError(f"无法读取 JSON：{path}: {exc}") from exc


def get_path(value: Any, dotted: str) -> Any:
    current = value
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def finding(check_id: str, status: str, message: str, severity: str = "error") -> dict[str, str]:
    return {
        "check_id": check_id,
        "status": status,
        "severity": severity if status in {"fail", "not_observed"} else "info",
        "message": message,
    }


def add(findings: list[dict[str, str]], check_id: str, status: str, message: str, severity: str = "error") -> None:
    findings.append(finding(check_id, status, message, severity))


def layer_summary(findings: list[dict[str, str]]) -> dict[str, Any]:
    observed = [item for item in findings if item["status"] in {"pass", "fail"}]
    passed = sum(item["status"] == "pass" for item in observed)
    failed = len(observed) - passed
    score = round(passed / len(observed), 4) if observed else None
    status = "not_observed" if not observed else ("fail" if failed else "pass")
    return {"status": status, "score": score, "passed": passed, "failed": failed, "coverage": len(observed), "findings": findings}


def validate_run(run: Any) -> None:
    if not isinstance(run, dict):
        raise EvalError("run 根节点必须是 JSON 对象")
    required = {"schema_version", "suite_id", "skill", "cases"}
    missing = required - run.keys()
    if missing:
        raise EvalError(f"run 缺少字段：{sorted(missing)}")
    if run["schema_version"] != RUN_VERSION:
        raise EvalError(f"schema_version 必须为 {RUN_VERSION}")
    if not isinstance(run["suite_id"], str) or not run["suite_id"]:
        raise EvalError("suite_id 必须是非空字符串")
    if not isinstance(run["skill"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", run["skill"]):
        raise EvalError("skill 必须是小写 kebab-case")
    if not isinstance(run["cases"], list) or not run["cases"]:
        raise EvalError("cases 必须是非空数组")
    for index, case in enumerate(run["cases"]):
        if not isinstance(case, dict):
            raise EvalError(f"cases[{index}] 必须是对象")
        for key in ("case_id", "task", "output"):
            if key not in case:
                raise EvalError(f"cases[{index}] 缺少字段：{key}")
        if not isinstance(case["case_id"], str) or not case["case_id"]:
            raise EvalError(f"cases[{index}].case_id 必须是非空字符串")
        if not isinstance(case["task"], dict):
            raise EvalError(f"cases[{index}].task 必须是对象")
        for key in ("expectations", "trajectory", "outcome"):
            if key in case and not isinstance(case[key], dict):
                raise EvalError(f"cases[{index}].{key} 必须是对象")


def parse_frontmatter(path: Path) -> tuple[set[str], set[str]]:
    skill_file = path / "SKILL.md" if path.is_dir() else path
    try:
        text = skill_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise EvalError(f"无法读取 Skill：{skill_file}: {exc}") from exc
    if not text.startswith("---"):
        return set(), set()
    parts = text.split("---", 2)
    if len(parts) < 3:
        return set(), set()
    keys: set[str] = set()
    metadata: set[str] = set()
    in_metadata = False
    for line in parts[1].splitlines():
        if re.match(r"^metadata\s*:", line):
            in_metadata = True
            continue
        if line and not line.startswith((" ", "\t")):
            in_metadata = False
        match = re.match(r"^\s{2}([A-Za-z0-9_-]+)\s*:", line)
        if match:
            key = match.group(1)
            if in_metadata:
                metadata.add(key)
            else:
                keys.add(key)
    return keys, metadata


def validate_known_output(output: Any, validator: str | None, findings: list[dict[str, str]]) -> None:
    if validator == "adaptive-pedagogy-result.v2":
        required = [
            "version", "mode", "decision.strategy", "decision.reason", "decision.question_value_gate",
            "student_response.text", "student_response.required_reply", "evidence_used", "state_update_proposals",
        ]
        for path in required:
            if get_path(output, path) is None:
                add(findings, "component.schema_validity", "fail", f"缺少 {path}")
        if get_path(output, "version") == validator:
            add(findings, "component.schema_version", "pass", f"版本匹配：{validator}")
        else:
            add(findings, "component.schema_version", "fail", f"version 必须为 {validator}")
        if isinstance(get_path(output, "evidence_used"), list):
            add(findings, "component.evidence_shape", "pass", "evidence_used 是数组")
    elif validator == "learner-state-reflector-result.v1":
        required = ["version", "evidence_summary", "state_update_proposals", "verification_debt_proposals"]
        for path in required:
            if get_path(output, path) is None:
                add(findings, "component.schema_validity", "fail", f"缺少 {path}")
        if get_path(output, "version") == validator:
            add(findings, "component.schema_version", "pass", f"版本匹配：{validator}")
        else:
            add(findings, "component.schema_version", "fail", f"version 必须为 {validator}")
    elif validator == "quiz-generation-result.v1":
        required = ["schema_version", "task_id", "title", "instructions", "questions", "total_points"]
        for path in required:
            if get_path(output, path) is None:
                add(findings, "component.schema_validity", "fail", f"缺少 {path}")
        if get_path(output, "schema_version") == validator:
            add(findings, "component.schema_version", "pass", f"版本匹配：{validator}")
        else:
            add(findings, "component.schema_version", "fail", f"schema_version 必须为 {validator}")
    elif validator == "curriculum-graph-builder-result.v1":
        required = ["schema_version", "task_id", "decision", "graph_patch", "warnings", "evidence_summary"]
        for path in required:
            if get_path(output, path) is None:
                add(findings, "component.schema_validity", "fail", f"缺少 {path}")
        if get_path(output, "schema_version") == validator:
            add(findings, "component.schema_version", "pass", f"版本匹配：{validator}")
        else:
            add(findings, "component.schema_version", "fail", f"schema_version 必须为 {validator}")
        patch = get_path(output, "graph_patch")
        if isinstance(patch, dict):
            required_patch_keys = {"add_nodes", "update_nodes", "add_edges", "update_edges", "learner_overlay_updates"}
            missing = required_patch_keys - patch.keys()
            if missing:
                add(findings, "component.graph_patch_shape", "fail", f"graph_patch 缺少：{sorted(missing)}")
            else:
                add(findings, "component.graph_patch_shape", "pass", "graph_patch 字段齐全")
            if any(key in patch for key in ("delete_nodes", "delete_edges")):
                add(findings, "component.no_destructive_patch", "fail", "v1 patch 不得包含删除操作")
            else:
                add(findings, "component.no_destructive_patch", "pass", "patch 不包含删除操作")
        else:
            add(findings, "component.graph_patch_shape", "fail", "graph_patch 必须是对象")
    elif validator == "html":
        html = output if isinstance(output, str) else get_path(output, "html")
        if not isinstance(html, str) or "<!doctype html>" not in html.lower() or "<html" not in html.lower():
            add(findings, "component.artifact_shape", "fail", "HTML 产物缺少 doctype 或 html 根元素")
        elif re.search(r"(?:src|href)\s*=\s*[\"']https?://", html, re.I):
            add(findings, "component.offline_artifact", "fail", "HTML 含外部网络依赖")
        else:
            add(findings, "component.artifact_shape", "pass", "HTML 是自包含文档")
    elif validator:
        add(findings, "component.validator", "not_observed", f"未内置 validator：{validator}", "warning")


def learner_text(output: Any, paths: list[str] | None) -> str:
    values: list[str] = []

    def collect(value: Any) -> None:
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                if key not in {"answer", "explanation", "keywords", "assumptions", "structured_data"}:
                    collect(item)

    if paths:
        for path in paths:
            collect(get_path(output, path))
    elif isinstance(output, str):
        collect(output)
    else:
        for path in ("student_response", "html", "public", "text"):
            value = get_path(output, path)
            if value is not None:
                collect(value)
    return "\n".join(values)


def evaluate_component(run: dict[str, Any], case: dict[str, Any], findings: list[dict[str, str]]) -> None:
    output = case["output"]
    if output is None:
        add(findings, "component.output_present", "fail", "output 不得为 null")
    else:
        add(findings, "component.output_present", "pass", "存在输出产物")
    expected = case.get("expectations", {})
    for path in expected.get("required_output_keys", []):
        if get_path(output, path) is None:
            add(findings, "component.required_output_keys", "fail", f"缺少 {path}")
    if expected.get("required_output_keys"):
        if all(get_path(output, path) is not None for path in expected["required_output_keys"]):
            add(findings, "component.required_output_keys", "pass", "自定义必需字段齐全")
    validator = case.get("validator")
    if validator:
        validate_known_output(output, validator, findings)
    else:
        add(findings, "component.contract", "not_observed", "未指定已知 validator 或自定义契约", "warning")
    skill_path = case.get("skill_path") or run.get("skill_path")
    if skill_path:
        _, metadata = parse_frontmatter(Path(skill_path))
        missing = REQUIRED_METADATA - metadata
        if missing:
            add(findings, "component.execution_metadata", "fail", f"SKILL.md 缺少 metadata：{sorted(missing)}")
        else:
            add(findings, "component.execution_metadata", "pass", "执行元数据齐全")
    else:
        add(findings, "component.execution_metadata", "not_observed", "未提供 skill_path，未检查 SKILL.md 元数据", "warning")


def evaluate_trajectory(case: dict[str, Any], findings: list[dict[str, str]]) -> None:
    trajectory = case.get("trajectory")
    if not trajectory:
        add(findings, "trajectory.present", "not_observed", "未提供执行轨迹", "warning")
        return
    turns = trajectory.get("turns", [])
    count = trajectory.get("learner_facing_writer_count")
    if count is None:
        count = sum(1 for turn in turns if isinstance(turn, dict) and turn.get("audience") == "learner" and turn.get("writer"))
    if count <= 1:
        add(findings, "trajectory.single_writer", "pass", "learner-facing writer 数量不超过 1")
    else:
        add(findings, "trajectory.single_writer", "fail", f"learner-facing writer 数量为 {count}")
    repeated = []
    previous: dict[str, Any] | None = None
    for turn in turns if isinstance(turns, list) else []:
        if not isinstance(turn, dict):
            continue
        question_id = turn.get("question_id")
        if question_id and previous and previous.get("question_id") == question_id and not turn.get("new_evidence"):
            repeated.append(question_id)
        previous = turn
        if (turn.get("sidecar") or turn.get("role") == "sidecar") and (turn.get("blocking") or turn.get("blocked_response")):
            add(findings, "trajectory.sidecar_nonblocking", "fail", "sidecar 阻塞了响应")
    if repeated:
        add(findings, "trajectory.repeated_question", "fail", f"无新证据重复提问：{sorted(set(repeated))}")
    else:
        add(findings, "trajectory.repeated_question", "pass", "未发现无新证据的连续重复提问")
    if trajectory.get("response_blocked_by_sidecar"):
        add(findings, "trajectory.sidecar_nonblocking", "fail", "响应被 sidecar 阻塞")
    else:
        add(findings, "trajectory.sidecar_nonblocking", "pass", "响应未被 sidecar 阻塞")
    expectations = case.get("expectations", {})
    for metric, label, limit in (
        ("blocking_hops", "blocking hop", expectations.get("max_blocking_hops")),
        ("latency_ms", "latency", expectations.get("max_latency_ms")),
    ):
        if limit is None:
            continue
        value = trajectory.get(metric)
        if isinstance(value, (int, float)) and value <= limit:
            add(findings, f"trajectory.{metric}", "pass", f"{label}={value} 不超过 {limit}")
        else:
            add(findings, f"trajectory.{metric}", "fail", f"{label}={value!r} 超过 {limit} 或缺失")
    token_limit = expectations.get("max_tokens")
    if token_limit is not None:
        tokens = trajectory.get("tokens")
        if tokens is None:
            tokens = (trajectory.get("prompt_tokens") or 0) + (trajectory.get("completion_tokens") or 0)
        if isinstance(tokens, (int, float)) and tokens <= token_limit:
            add(findings, "trajectory.tokens", "pass", f"tokens={tokens} 不超过 {token_limit}")
        else:
            add(findings, "trajectory.tokens", "fail", f"tokens={tokens!r} 超过 {token_limit} 或缺失")


def evaluate_pedagogy(case: dict[str, Any], findings: list[dict[str, str]]) -> None:
    output = case["output"]
    expected = case.get("expectations", {})
    text = learner_text(output, expected.get("learner_facing_paths"))
    forbidden = [str(item) for item in expected.get("forbidden_strings", []) + expected.get("answer_tokens", [])]
    leaked = [item for item in forbidden if item and item.casefold() in text.casefold()]
    if forbidden:
        if leaked:
            add(findings, "pedagogy.answer_leakage", "fail", f"learner-facing 内容泄露：{leaked}")
        else:
            add(findings, "pedagogy.answer_leakage", "pass", "未发现预设泄题字符串")
    else:
        add(findings, "pedagogy.answer_leakage", "not_observed", "未提供泄题词表", "warning")
    evidence_ids = set(str(item) for item in expected.get("evidence_ids", []))
    used = get_path(output, "evidence_used")
    if expected.get("require_evidence"):
        if not isinstance(used, list) or not used:
            add(findings, "pedagogy.evidence_grounding", "fail", "要求证据但 evidence_used 为空")
        elif evidence_ids and not set(map(str, used)).issubset(evidence_ids):
            add(findings, "pedagogy.evidence_grounding", "fail", "evidence_used 含未在 case 中声明的证据 ID")
        else:
            add(findings, "pedagogy.evidence_grounding", "pass", "输出引用了声明范围内的证据")
    else:
        add(findings, "pedagogy.evidence_grounding", "not_observed", "未要求证据绑定", "warning")
    scaffolds = get_path(output, "student_response.local_scaffolds")
    if scaffolds is not None:
        max_hints = expected.get("max_hint_count", 3)
        if isinstance(scaffolds, list) and len(scaffolds) <= max_hints:
            add(findings, "pedagogy.hint_limit", "pass", f"局部提示数量为 {len(scaffolds)}")
        else:
            add(findings, "pedagogy.hint_limit", "fail", f"局部提示超过上限 {max_hints}")
    else:
        add(findings, "pedagogy.hint_limit", "not_observed", "未提供 local_scaffolds", "warning")
    gate = get_path(output, "decision.question_value_gate")
    required_reply = get_path(output, "student_response.required_reply")
    if gate == "do_not_ask" and required_reply is True:
        add(findings, "pedagogy.question_value", "fail", "question_value_gate=do_not_ask 但要求 learner 回复")
    elif gate is not None:
        add(findings, "pedagogy.question_value", "pass", "问题价值门控与回复要求一致")
    else:
        add(findings, "pedagogy.question_value", "not_observed", "未提供问题价值门控", "warning")
    action_limit = expected.get("max_required_actions")
    if action_limit is not None:
        action_count = 1 if required_reply is True else 0
        if action_count <= action_limit:
            add(findings, "pedagogy.required_actions", "pass", f"mandatory learner action 数量为 {action_count}")
        else:
            add(findings, "pedagogy.required_actions", "fail", f"mandatory learner action 数量为 {action_count}，超过 {action_limit}")
    visual = get_path(output, "visual_request")
    if isinstance(visual, dict) and visual.get("blocking") is True and not visual.get("fallback_text"):
        add(findings, "pedagogy.visual_fallback", "fail", "阻塞式 visual_request 缺少 fallback_text")
    elif isinstance(visual, dict):
        add(findings, "pedagogy.visual_fallback", "pass", "visual 请求可在文本 fallback 下异步执行")
    else:
        add(findings, "pedagogy.visual_fallback", "not_observed", "未请求 visual artifact", "warning")


def evaluate_outcome(case: dict[str, Any], findings: list[dict[str, str]]) -> None:
    outcome = case.get("outcome")
    if not outcome:
        add(findings, "learner_outcome.present", "not_observed", "未提供学习结果", "warning")
        return
    passed = outcome.get("independent_transfer_passed")
    if passed is True:
        add(findings, "learner_outcome.independent_transfer", "pass", "独立迁移任务通过")
    elif passed is False:
        add(findings, "learner_outcome.independent_transfer", "fail", "独立迁移任务未通过")
    else:
        add(findings, "learner_outcome.independent_transfer", "not_observed", "未提供独立迁移结果", "warning")
    baseline = outcome.get("baseline_score")
    posttest = outcome.get("posttest_score")
    if isinstance(baseline, (int, float)) and isinstance(posttest, (int, float)):
        gain = posttest - baseline
        threshold = case.get("expectations", {}).get("min_score_gain")
        if threshold is None or gain >= threshold:
            add(findings, "learner_outcome.score_gain", "pass", f"score gain={gain:.4g}")
        else:
            add(findings, "learner_outcome.score_gain", "fail", f"score gain={gain:.4g} 小于 {threshold}")
    else:
        add(findings, "learner_outcome.score_gain", "not_observed", "未同时提供 baseline_score 和 posttest_score", "warning")
    expectations = case.get("expectations", {})
    if expectations.get("verification_debt_should_discharge"):
        if outcome.get("verification_debt_discharged") is True:
            add(findings, "learner_outcome.verification_debt", "pass", "verification debt 已由独立证据解除")
        else:
            add(findings, "learner_outcome.verification_debt", "fail", "要求解除 verification debt 但未提供独立证据")
    if expectations.get("traceability_required"):
        if isinstance(outcome.get("evidence_refs"), list) and outcome["evidence_refs"]:
            add(findings, "learner_outcome.traceability", "pass", "学习结果带有 evidence_refs")
        else:
            add(findings, "learner_outcome.traceability", "fail", "学习结果缺少 evidence_refs")


def evaluate(run: dict[str, Any]) -> dict[str, Any]:
    validate_run(run)
    case_reports: list[dict[str, Any]] = []
    for case in run["cases"]:
        layers: dict[str, dict[str, Any]] = {}
        for name, evaluator in (
            ("component", evaluate_component),
            ("trajectory", evaluate_trajectory),
            ("pedagogy", evaluate_pedagogy),
            ("learner_outcome", evaluate_outcome),
        ):
            findings: list[dict[str, str]] = []
            evaluator(run, case, findings) if name == "component" else evaluator(case, findings)
            layers[name] = layer_summary(findings)
        observed_scores = [layer["score"] for layer in layers.values() if layer["score"] is not None]
        score = round(sum(observed_scores) / len(observed_scores), 4) if observed_scores else None
        hard_fail = any(layer["status"] == "fail" for layer in layers.values())
        case_reports.append({
            "case_id": case["case_id"],
            "status": "fail" if hard_fail else ("pass" if score is not None else "not_observed"),
            "score": score,
            "thresholds": case.get("expectations", {}),
            "metrics": {
                "trajectory": {
                    key: case.get("trajectory", {}).get(key)
                    for key in ("learner_facing_writer_count", "blocking_hops", "latency_ms", "prompt_tokens", "completion_tokens", "tokens")
                    if key in case.get("trajectory", {})
                },
                "outcome": {
                    key: case.get("outcome", {}).get(key)
                    for key in ("baseline_score", "posttest_score", "independent_transfer_passed", "verification_debt_discharged")
                    if key in case.get("outcome", {})
                },
            },
            "layers": layers,
        })
    scores = [item["score"] for item in case_reports if item["score"] is not None]
    failed_cases = sum(item["status"] == "fail" for item in case_reports)
    return {
        "schema_version": REPORT_VERSION,
        "suite_id": run["suite_id"],
        "skill": run["skill"],
        "status": "fail" if failed_cases else "pass",
        "summary": {
            "case_count": len(case_reports),
            "passed_cases": len(case_reports) - failed_cases,
            "failed_cases": failed_cases,
            "score": round(sum(scores) / len(scores), 4) if scores else None,
        },
        "cases": case_reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a skill-eval-run.v1 file")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate-run", "evaluate"):
        command = sub.add_parser(name)
        command.add_argument("run")
        if name == "evaluate":
            command.add_argument("-o", "--output")
    args = parser.parse_args()
    try:
        run = load_json(args.run)
        validate_run(run)
        if args.command == "validate-run":
            print(f"校验通过：{RUN_VERSION}")
        else:
            report = json.dumps(evaluate(run), ensure_ascii=False, indent=2) + "\n"
            if args.output:
                Path(args.output).write_text(report, encoding="utf-8")
            else:
                sys.stdout.write(report)
        return 0
    except (EvalError, OSError) as exc:
        print(f"校验失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
