#!/usr/bin/env python3
"""Explicit DeepSeek integration smoke test.

This script never calls the provider unless ``--live`` is supplied. The API
server must already be running and must load ``DS_API_KEY`` from ``.env``.

    python scripts/agent_smoke.py --live --base http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Any

import httpx


REQUIRED_EVENTS = {
    "task.started",
    "intent.started",
    "intent.completed",
    "agent.started",
    "agent.completed",
    "artifact.ready",
    "task.completed",
}


def parse_sse(body: str) -> tuple[list[dict[str, Any]], str]:
    events: list[dict[str, Any]] = []
    current_kind = ""
    for line in body.splitlines():
        if line.startswith("event: "):
            current_kind = line[7:]
        elif line.startswith("data: "):
            value = json.loads(line[6:])
            if current_kind != "stream.end":
                events.append(value)
    return events, current_kind


def run(base: str, prompt: str, timeout: float) -> int:
    with httpx.Client(base_url=base.rstrip("/"), timeout=30.0) as client:
        health = client.get("/api/health")
        health.raise_for_status()
        if not health.json().get("agent", {}).get("configured"):
            raise RuntimeError("server is not configured with DS_API_KEY")

        created = client.post("/api/agent-tasks", json={"prompt": prompt})
        created.raise_for_status()
        task_id = created.json()["id"]
        print(f"task={task_id}")

        deadline = time.monotonic() + timeout
        snapshot: dict[str, Any] = {}
        while time.monotonic() < deadline:
            response = client.get(f"/api/agent-tasks/{task_id}")
            response.raise_for_status()
            snapshot = response.json()
            print(f"status={snapshot['status']}")
            if snapshot["status"] in {"completed", "partial", "failed"}:
                break
            time.sleep(2)

        if snapshot.get("status") != "completed":
            raise RuntimeError(f"agent task did not complete: {snapshot.get('error', snapshot)}")
        if not snapshot["artifacts"]["background"]["available"]:
            raise RuntimeError("background artifact is missing")
        if not snapshot["artifacts"]["visual"]["available"]:
            raise RuntimeError("visual artifact is missing")

        stream = client.get(f"/api/agent-tasks/{task_id}/events")
        stream.raise_for_status()
        events, end_kind = parse_sse(stream.text)
        kinds = {event["kind"] for event in events}
        missing = REQUIRED_EVENTS - kinds
        if missing or end_kind != "stream.end":
            raise RuntimeError(f"SSE event contract failed: missing={sorted(missing)} end={end_kind}")

        background = client.get(f"/api/agent-tasks/{task_id}/artifacts/background")
        visual = client.get(f"/api/agent-tasks/{task_id}/artifacts/visual")
        if background.status_code != 200 or visual.status_code != 200:
            raise RuntimeError("one or more artifact endpoints failed")
        if "## 开场" not in background.text or "<!doctype html>" not in visual.text.lower():
            raise RuntimeError("artifact content does not match the expected formats")

        print(f"PASS: completed with {len(events)} durable SSE events")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="enable the real DeepSeek request")
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--prompt", default="解释 TCP 拥塞控制并生成两份学习产物")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    if not args.live:
        print("Refusing to call DeepSeek. Re-run with --live to enable integration smoke.")
        return 2
    try:
        return run(args.base, args.prompt, args.timeout)
    except (httpx.HTTPError, RuntimeError) as exc:
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
