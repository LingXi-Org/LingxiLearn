from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "server"))

@pytest.fixture(scope="session")
def registry():
    from lingxilearn.tools.registry import load_builtin_tools

    return load_builtin_tools()
