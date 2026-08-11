#!/usr/bin/env python3
"""Regenerate the teaching captures and print their ground truth.

The pcap files are build output, not source — they are in ``.gitignore`` and
rebuilt from ``lingxilearn.tools.net.synth``.  Keeping the generator in version
control rather than the bytes means the ground truth is reviewable.

    python scripts/build_artifacts.py [--check]

``--check`` re-derives the waterfall from the freshly written file and asserts
it matches the generator's intent, so a change to either the synthesiser or the
parser that breaks the other one fails loudly.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "server"))

from lingxilearn.tools.net import analysis, pcapfile, synth  # noqa: E402

TARGETS = [
    ("web-slow", REPO_ROOT / "packs/computer-networks/missions/web-slow/artifacts/web-slow.pcap"),
    (
        "dns-nxdomain",
        REPO_ROOT / "packs/computer-networks/missions/web-slow/artifacts/dns-nxdomain.pcap",
    ),
]

EXPECTED = {
    "web-slow": {
        "dns": 121.4,
        "tcp_connect": 31.9,
        "ttfb": 188.6,
        "transfer": 19.2,
        "retransmission": 225.8,
    }
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify ground truth after writing")
    args = parser.parse_args()

    failures = 0
    for scenario, path in TARGETS:
        info = synth.generate(scenario, path)
        print(f"[ok]   {scenario:14} {info['frames']:>3} frames  →  {path.relative_to(REPO_ROOT)}")

        if not args.check:
            continue
        frames = pcapfile.read_pcap(path)
        if len(frames) != info["frames"]:
            print(f"[FAIL] {scenario}: wrote {info['frames']} frames, read back {len(frames)}")
            failures += 1
            continue
        if scenario not in EXPECTED:
            continue
        buckets = analysis.waterfall(frames)["buckets"]
        for name, want in EXPECTED[scenario].items():
            got = buckets.get(name, 0.0)
            if abs(got - want) > 0.5:
                print(f"[FAIL] {scenario}.{name}: expected {want} ms, parser derived {got} ms")
                failures += 1
        print(f"       ground truth: {json.dumps(buckets, ensure_ascii=False)}")

    if failures:
        print(f"\n{failures} check(s) failed.")
        return 1
    if args.check:
        print("\nAll captures round-trip and match their declared ground truth.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
