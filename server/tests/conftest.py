from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "server"))

PACK_DIR = REPO_ROOT / "packs" / "computer-networks"


@pytest.fixture(scope="session")
def pack_dir() -> Path:
    return PACK_DIR


@pytest.fixture(scope="session")
def registry():
    from lingxilearn.tools.registry import load_builtin_tools

    return load_builtin_tools()


@pytest.fixture(scope="session")
def pack(pack_dir):
    from lingxilearn.packs.loader import load_pack

    return load_pack(pack_dir)


@pytest.fixture(scope="session")
def capture(tmp_path_factory) -> Path:
    """A freshly synthesised capture — never a checked-in binary."""
    from lingxilearn.tools.net import synth

    target = tmp_path_factory.mktemp("captures") / "web-slow.pcap"
    synth.generate("web-slow", target)
    return target
