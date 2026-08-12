#!/usr/bin/env python3
"""Small deterministic baseline for testing policy routing.

This is deliberately conservative and is not a psychometric model.
The production Skill may use richer LLM reasoning, but the same routing principles apply.
"""
import json, sys

def choose(event, state):
    event = event or {}
    correct = event.get("correct")
    attempts = int(event.get("attempts", 1))
    confidence = event.get("confidence")
    stable_rule = bool(event.get("stable_incorrect_rule", False))
    asked_explain = event.get("support_choice") == "direct_explain"
    hint_level = event.get("hint_level", 0) or 0
    checkpoint = bool(event.get("checkpoint", False))
    model_challenge = bool(event.get("learner_model_challenge", False))

    if model_challenge:
        return "learner_model_challenge"
    if asked_explain:
        return "targeted_explanation"
    if checkpoint and state.get("verification_debt"):
        return "transfer_check"
    if correct is True:
        # Don't interrogate a learner who has already demonstrated the relation.
        return "advance"
    if correct is False and stable_rule and confidence is not None and confidence >= 0.7:
        return "conceptual_conflict"
    if correct is False and (attempts >= 2 or hint_level >= 2):
        return "worked_example_fade"
    if correct is False:
        return "progressive_hint"
    return "retrieve_or_predict"

def main():
    data = json.load(sys.stdin) if len(sys.argv) == 1 else json.load(open(sys.argv[1], encoding="utf-8"))
    print(json.dumps({"strategy": choose(data.get("current_event"), data.get("learner_state", {}))},
                     ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
