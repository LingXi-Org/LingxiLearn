from pathlib import Path

from lingxilearn.state.capabilities import Capability
from lingxilearn.state.skill_catalog import discover


SKILLS = Path(__file__).resolve().parents[2] / "skills"


def test_realtime_conversation_capabilities_are_registry_backed() -> None:
    manifests = {manifest.skill_id: manifest for manifest in discover(SKILLS)}
    assert str(Capability.DIALOG_CONVERSE) in {
        str(capability) for capability in manifests["learning-companion"].capabilities
    }
    assert str(Capability.DIALOG_PROBE) in {
        str(capability) for capability in manifests["socratic-prober"].capabilities
    }
    assert manifests["learning-companion"].cost["blocking"] is False


def test_every_discovered_skill_has_a_user_safe_status_line() -> None:
    assert all(manifest.status_line.strip() for manifest in discover(SKILLS))
