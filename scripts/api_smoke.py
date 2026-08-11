#!/usr/bin/env python3
"""Drive a whole mission over the HTTP API, including SSE.

    python scripts/api_smoke.py --base http://localhost:8000 --mission web-slow

Checks the things that only break over the wire: that the pending question is
readable from durable state (not held in a socket), that answering resumes the
run, that the event stream replays from ``Last-Event-ID`` after a deliberate
disconnect, and that the answer key never crosses the wire.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "server"))

from lingxilearn.tools.net import sim  # noqa: E402

_failures: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"{'[PASS]' if ok else '[FAIL]'} {label}" + (f"  — {detail}" if detail else ""))
    if not ok:
        _failures.append(label)


TRUTH = {"dns": 121.4, "tcp_connect": 31.9, "ttfb": 188.6, "transfer": 19.2, "retransmission": 225.8}
PINS = {
    "dns": [1, 2], "tcp_connect": [3, 4, 5], "ttfb": [6, 7],
    "transfer": [8, 9, 10], "retransmission": [12, 13, 14],
}
CHOICES = {
    "web-slow": {"p1": "a", "p2": "b", "p3": "b", "v1": "c", "v2": "b",
                 "orient": "b", "stall": "b"},
    "reliable-delivery": {"p1": "b", "p2": "b", "p3": "b", "v1": "b", "v2": "b",
                          "read-the-console": "a", "debrief": "b"},
}


def reply_for(pending: dict[str, Any], mission: str) -> Any:
    value = pending["value"]
    table = CHOICES[mission]
    if value.get("kind") in ("probe", "verify"):
        return {i["id"]: {"choice": table.get(i["id"], "a")} for i in value["items"]}
    expects = (value.get("prompt") or {}).get("expects", "text")
    if expects == "attribution":
        return {"allocations": TRUTH, "pins": PINS}
    if expects == "sim_action":
        return {"actions": sim.oracle("single-loss", 7)["actions"]}
    return {"choice": table.get(value.get("step_id", ""), "b")}


async def wait_for_pause(client: httpx.AsyncClient, base: str, sid: str) -> dict[str, Any]:
    for _ in range(300):
        snap = (await client.get(f"{base}/api/sessions/{sid}")).json()
        if snap["status"] != "running":
            return snap
        await asyncio.sleep(0.1)
    raise TimeoutError("session never left running")


async def collect_sse(base: str, sid: str, *, last_id: int = 0, stop_after: int = 6) -> list[dict]:
    """Read a few events then hang up — mimicking a flaky client."""
    got: list[dict[str, Any]] = []
    headers = {"Last-Event-ID": str(last_id)} if last_id else {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        async with client.stream(
            "GET", f"{base}/api/sessions/{sid}/events", headers=headers
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    got.append(json.loads(line[6:]))
                    if len(got) >= stop_after:
                        return got
                if line.startswith("event: stream.end"):
                    return got
    return got


async def run(base: str, mission: str) -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        health = (await client.get(f"{base}/api/health")).json()
        check(health["status"] == "ok", "API healthy", f"brain={health['brain']}")

        created = await client.post(
            f"{base}/api/sessions", json={"mission_id": mission, "pack_id": "computer-networks"}
        )
        check(created.status_code == 201, "session created", created.text[:80])
        sid = created.json()["id"]
        learner = created.json()["learner_id"]

        first = await collect_sse(base, sid, stop_after=4)
        check(bool(first), "SSE delivered events", f"{len(first)} before hangup")

        snap = await wait_for_pause(client, base, sid)
        check(snap["status"] == "awaiting_learner", "run paused for the learner", snap["status"])
        check(snap["pending"] is not None, "pending question readable from durable state")

        # Reconnect from where the first reader stopped.
        resumed = await collect_sse(base, sid, last_id=first[-1]["sequence"], stop_after=3)
        check(
            all(e["sequence"] > first[-1]["sequence"] for e in resumed),
            "SSE resumed after Last-Event-ID",
            f"from {first[-1]['sequence']} → {[e['sequence'] for e in resumed]}",
        )

        turns = 0
        while snap["status"] == "awaiting_learner" and turns < 30:
            turns += 1
            body = {"answer": reply_for(snap["pending"], mission)}
            accepted = await client.post(f"{base}/api/sessions/{sid}/answer", json=body)
            check(accepted.status_code == 202, f"answer {turns} accepted", accepted.text[:60]) if (
                turns == 1
            ) else None
            snap = await wait_for_pause(client, base, sid)

        check(snap["status"] == "done", "mission completed over HTTP", f"{turns} turns")

        leaked = json.dumps(snap, ensure_ascii=False)
        check("grader" not in leaked, "answer key never crosses the wire")
        check("walkthrough" not in leaked or snap.get("answer_unlocked"),
              "walkthrough withheld while locked")

        report = (await client.get(f"{base}/api/sessions/{sid}/report")).json()
        check("headline" in report, "report retrievable", report.get("headline", "")[:60])
        check(
            report.get("verify_score", 0) >= 0.9,
            "post-test passed",
            f"probe {report.get('probe_score')} → verify {report.get('verify_score')}",
        )

        mastery = (await client.get(f"{base}/api/learners/{learner}/mastery")).json()
        check(bool(mastery["mastery"]), "mastery persisted across the session",
              f"{len(mastery['mastery'])} concepts")

        events = await collect_sse(base, sid, stop_after=10_000)
        kinds = {e["kind"] for e in events}
        check("tool.completed" in kinds, "tool events recorded", f"{len(events)} total events")
        check("report.ready" in kinds, "report event recorded")

        if mission == "web-slow":
            art = await client.get(f"{base}/api/sessions/{sid}/artifact/capture")
            check(
                art.status_code == 200 and art.content[:4].hex() == "d4c3b2a1",
                "raw capture downloadable and valid",
                f"{len(art.content)} bytes",
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--mission", default="web-slow")
    args = parser.parse_args()
    print(f"=== LingxiLearn API smoke · {args.base} · mission={args.mission} ===")
    asyncio.run(run(args.base, args.mission))
    print()
    print("RESULT:", "FAILED — " + ", ".join(_failures) if _failures else "all checks passed")
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
