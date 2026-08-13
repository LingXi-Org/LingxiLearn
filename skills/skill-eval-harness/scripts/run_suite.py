#!/usr/bin/env python3
"""Run every checked-in skill-eval-run.v1 suite under a repository."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evaluate import EvalError, evaluate, load_json, validate_run


SUITE_REPORT_VERSION = "skill-eval-suite-report.v1"


def normalize_paths(run: dict, root: Path) -> dict:
    normalized = json.loads(json.dumps(run))
    for container in (normalized, *normalized.get("cases", [])):
        path = container.get("skill_path") if isinstance(container, dict) else None
        if path and not Path(path).is_absolute():
            container["skill_path"] = str((root / path).resolve())
    return normalized


def discover(root: Path) -> list[Path]:
    return sorted(root.glob("skills/*/assets/eval-run.json"))


def run(root: Path) -> dict:
    reports = []
    errors = []
    for path in discover(root):
        try:
            suite = normalize_paths(load_json(path), root)
            validate_run(suite)
            report = evaluate(suite)
            report["source"] = str(path.relative_to(root))
            reports.append(report)
        except (EvalError, OSError, ValueError) as exc:
            errors.append({"source": str(path.relative_to(root)), "error": str(exc)})
    failed = sum(report["status"] == "fail" for report in reports) + len(errors)
    case_count = sum(report["summary"]["case_count"] for report in reports)
    return {
        "schema_version": SUITE_REPORT_VERSION,
        "status": "fail" if failed else "pass",
        "summary": {
            "suite_count": len(reports),
            "case_count": case_count,
            "failed_suites": failed,
            "score": round(sum(report["summary"]["score"] or 0 for report in reports) / len(reports), 4) if reports else None,
        },
        "suites": reports,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("-o", "--output")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report = json.dumps(run(root), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
    else:
        sys.stdout.write(report)
    return 0 if json.loads(report)["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
