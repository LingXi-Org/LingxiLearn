#!/usr/bin/env python3
"""Dependency-free structural validator for lecture-hook-result.v1 outputs."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from urllib.parse import urlparse


def fail(msg: str) -> None:
    raise ValueError(msg)


def require(obj, key, typ=None):
    if key not in obj:
        fail(f"missing required key: {key}")
    if typ is not None and not isinstance(obj[key], typ):
        fail(f"{key} must be {typ.__name__}")
    return obj[key]


def validate(data: dict) -> None:
    if data.get("schema_version") != "lecture-hook-result.v1":
        fail("schema_version must be lecture-hook-result.v1")
    if data.get("status") not in {"ok", "insufficient_evidence"}:
        fail("invalid status")
    require(data, "topic", str)
    hook = require(data, "selected_hook", dict)
    for key in ("title", "hook_type", "opening", "story", "question", "transition", "why_this_hook_works"):
        require(hook, key, str)
    dur = require(hook, "estimated_duration_sec", int)
    if not 10 <= dur <= 180:
        fail("estimated_duration_sec out of range")

    candidates = require(data, "candidates", list)
    if not candidates:
        fail("candidates must not be empty")
    for i, c in enumerate(candidates):
        if not isinstance(c, dict):
            fail(f"candidate {i} must be an object")
        for key in ("title", "hook_type"):
            require(c, key, str)
        for key in ("score", "lesson_alignment", "curiosity", "evidence_strength"):
            value = require(c, key, (int, float))
            if not 0 <= value <= 100:
                fail(f"candidate {i}.{key} out of range")

    research = require(data, "research", dict)
    claims = require(research, "claims", list)
    sources = require(research, "sources", list)
    require(research, "search_angles", list)
    source_ids = set()
    for i, s in enumerate(sources):
        sid = require(s, "source_id", str)
        source_ids.add(sid)
        url = require(s, "url", str)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            fail(f"source {i} has invalid URL")
        if s.get("tier") not in {"A", "B", "C", "D"}:
            fail(f"source {i} has invalid tier")

    for i, c in enumerate(claims):
        require(c, "claim_id", str)
        require(c, "claim", str)
        if c.get("status") not in {"verified", "qualified", "rejected"}:
            fail(f"claim {i} has invalid status")
        conf = c.get("confidence")
        if not isinstance(conf, (int, float)) or not 0 <= conf <= 1:
            fail(f"claim {i} confidence out of range")
        ids = require(c, "source_ids", list)
        unknown = [x for x in ids if x not in source_ids]
        if unknown:
            fail(f"claim {i} references unknown sources: {unknown}")

    require(data, "warnings", list)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate_output.py RESULT.json", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            fail("root must be an object")
        validate(data)
    except Exception as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print("VALID lecture-hook-result.v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
