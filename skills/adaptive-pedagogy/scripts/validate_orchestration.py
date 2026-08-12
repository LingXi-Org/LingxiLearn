#!/usr/bin/env python3
"""Validate a simple orchestration-plan JSON for latency-safe defaults."""
import json, sys

def main(path):
    p = json.load(open(path, encoding="utf-8"))
    blocking = [x for x in p.get("jobs", []) if x.get("blocking")]
    if len(blocking) > 1:
        raise SystemExit(f"FAIL: {len(blocking)} blocking jobs; normal budget is 1")
    names = {x.get("skill") for x in p.get("jobs", [])}
    forbidden = {
        "student-model-builder", "productive-struggle", "conceptual-conflict",
        "epistemic-calibration", "teach-back", "learner-model-negotiation"
    }
    hit = names & forbidden
    if hit:
        raise SystemExit("FAIL: v0.1 micro-skills on runtime graph: " + ", ".join(sorted(hit)))
    print("PASS")

if __name__ == "__main__":
    main(sys.argv[1])
