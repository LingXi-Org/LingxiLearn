#!/usr/bin/env python3
import json, sys

ALLOWED_EXTERNAL = {"interactive-visual-explainer", "interactive-lecture-deck", "learner-state-reflector"}

def fail(msg):
    print("FAIL:", msg)
    raise SystemExit(1)

def main(path):
    data = json.load(open(path, encoding="utf-8"))
    if data.get("version") != "adaptive-pedagogy-result.v2":
        fail("wrong version")
    sr = data.get("student_response") or {}
    scaffolds = sr.get("local_scaffolds") or []
    if len(scaffolds) > 3:
        fail("more than 3 local scaffolds")
    levels = [x.get("level", 0) for x in scaffolds]
    if levels != sorted(levels):
        fail("local scaffold levels must increase")
    if data.get("mode") == "preflight" and sr.get("required_reply"):
        fail("preflight cannot require learner reply")
    vr = data.get("visual_request")
    if vr:
        if vr.get("skill") != "interactive-visual-explainer":
            fail("visual_request must target interactive-visual-explainer")
        if not vr.get("blocking", False) and not vr.get("fallback_text"):
            fail("non-blocking visual request needs fallback_text")
    bg = data.get("background_reflection")
    if bg and bg.get("blocking", False):
        fail("background_reflection must be non-blocking")
    delegated = data.get("delegations") or []
    for d in delegated:
        if d.get("skill") not in ALLOWED_EXTERNAL:
            fail(f"blocking micro-strategy delegation not allowed: {d.get('skill')}")
    print("PASS")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: validate_result.py <result.json>")
        raise SystemExit(2)
    main(sys.argv[1])
