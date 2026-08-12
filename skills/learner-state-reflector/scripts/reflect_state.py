#!/usr/bin/env python3
"""Minimal event compressor for smoke tests; not a mastery estimator."""
import json, sys
from collections import defaultdict

def main(path):
    data = json.load(open(path, encoding="utf-8"))
    grouped = defaultdict(list)
    for e in data.get("events", []):
        concept = e.get("concept", "unknown")
        grouped[concept].append(e)

    summary = []
    debts = []
    for concept, events in grouped.items():
        independent_correct = any(e.get("correct") is True and not e.get("assisted", False) for e in events)
        repeated_wrong_rule = sum(1 for e in events if e.get("stable_incorrect_rule")) >= 1
        strong_help = any((e.get("hint_level", 0) or 0) >= 3 or e.get("solution_shown") for e in events)

        if independent_correct:
            status = "demonstrated"
        elif repeated_wrong_rule:
            status = "misconception_evidence"
        elif strong_help:
            status = "needs_recheck"
        else:
            status = "emerging"

        ids = [e.get("id") for e in events if e.get("id")]
        summary.append({"concept": concept, "status": status, "evidence_ids": ids})
        if strong_help and not independent_correct:
            debts.append({"concept": concept, "reason": "high_reveal_help_without_independent_evidence",
                          "evidence_ids": ids})

    out = {
        "version": "learner-state-reflector-result.v1",
        "evidence_summary": summary,
        "state_update_proposals": [],
        "verification_debt_proposals": debts,
        "learner_model_card": None,
        "prefetch_suggestions": None
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: reflect_state.py <task.json>")
    main(sys.argv[1])
