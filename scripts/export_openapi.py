#!/usr/bin/env python3
"""Deterministic OpenAPI export for the LingxiLearn REST surface.

Produces ``var/openapi/rest-contracts.json`` — a sorted, stable JSON document
that the TypeScript code-generator (``web/scripts/generate-rest-contracts.ts``)
consumes to produce the frontend Zod contract layer.

The export is deterministic: identical code always produces identical bytes.
This lets CI diff the file and reject any PR that changes the wire contract
without also committing the regenerated document (drift gate).

Usage:
    python scripts/export_openapi.py                  # write + exit 0
    python scripts/export_openapi.py --check           # exit 1 if stale
    python scripts/export_openapi.py --stdout           # print to stdout
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Ensure the ``server/`` package is importable when running from the repo root.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SERVER_DIR = os.path.join(_REPO_ROOT, "server")
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

_OUTPUT_REL = os.path.join("var", "openapi", "rest-contracts.json")


def _generate() -> dict:
    from lingxilearn.main import app  # imported lazily inside the function

    return app.openapi()


def _serialize(schema: dict) -> str:
    """Serialize with deterministic key order and stable formatting."""
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _output_path() -> str:
    return os.path.join(_REPO_ROOT, _OUTPUT_REL)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export OpenAPI JSON")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if the on-disk file is stale instead of writing",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print to stdout instead of writing to disk",
    )
    args = parser.parse_args()

    schema = _generate()
    blob = _serialize(schema)

    if args.stdout:
        sys.stdout.write(blob)
        return 0

    target = _output_path()
    if args.check:
        if not os.path.isfile(target):
            print(f"MISSING  {target}", file=sys.stderr)
            return 1
        with open(target, encoding="utf-8") as fh:
            existing = fh.read()
        if existing != blob:
            print(f"STALE    {target}  — re-run: python scripts/export_openapi.py", file=sys.stderr)
            return 1
        paths = len(schema.get("paths", {}))
        schemas = len(schema.get("components", {}).get("schemas", {}))
        print(f"OK       {target}  ({paths} paths, {schemas} schemas)")
        return 0

    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(blob)
    paths = len(schema.get("paths", {}))
    schemas = len(schema.get("components", {}).get("schemas", {}))
    print(f"WROTE    {target}  ({paths} paths, {schemas} schemas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
