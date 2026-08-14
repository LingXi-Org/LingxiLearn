"""The capability registry, seeded from the SKILL.md manifests on disk."""

from __future__ import annotations

from pathlib import Path

import pytest

from lingxilearn.state.capabilities import Capability, UnknownCapability, parse
from lingxilearn.state.skill_catalog import (
    SkillManifestError,
    discover,
    parse_manifest,
    split_frontmatter,
)

SKILLS_ROOT = Path(__file__).resolve().parents[2] / "skills"


def test_every_shipped_skill_parses() -> None:
    manifests = discover(SKILLS_ROOT)
    assert len(manifests) >= 20
    assert all(m.skill_id for m in manifests)
    assert all(m.version for m in manifests)


def test_every_shipped_skill_also_loads_in_the_lingxigraph_runtime() -> None:
    """Two parsers read these files, and the stricter one sets the format.

    LingxiGraph's frontmatter reader only accepts scalar ``key: value`` pairs
    under ``metadata`` — no block sequences, no flow collections, and exactly
    two spaces of indent.  ``capabilities`` is therefore a comma-separated
    scalar.  Without this test the registry keeps parsing fine while every
    skill-loading agent breaks at run time.
    """

    from lingxigraph import FilesystemSkillSource

    failures: list[str] = []
    for directory in sorted(item for item in SKILLS_ROOT.iterdir() if item.is_dir()):
        if not (directory / "SKILL.md").is_file():
            continue
        try:
            FilesystemSkillSource(directory).discover()
        except Exception as exc:  # noqa: BLE001 - the message is the assertion
            failures.append(f"{directory.name}: {exc}")
    assert not failures, "SKILL.md files unreadable by the LingxiGraph runtime: " + "; ".join(
        failures
    )


def test_every_capability_has_at_least_one_provider() -> None:
    """A capability nobody can serve is a planning dead end."""

    provided: set[str] = set()
    for manifest in discover(SKILLS_ROOT):
        provided.update(str(c) for c in manifest.capabilities)

    missing = sorted({str(c) for c in Capability} - provided)
    assert not missing, f"no skill provides these capabilities: {missing}"


def test_dedicated_skills_declare_a_capability_and_a_provider() -> None:
    for manifest in discover(SKILLS_ROOT):
        if manifest.ownership != "dedicated":
            continue
        assert manifest.capabilities, f"{manifest.skill_id} is dedicated but declares no capability"
        assert manifest.provider, f"{manifest.skill_id} is dedicated but names no provider"


def test_shared_skills_are_not_plannable() -> None:
    """Shared skills are composed into providers; they must never be selectable."""

    shared = [m for m in discover(SKILLS_ROOT) if m.ownership == "shared"]
    assert shared, "expected the cross-cutting shared skills to exist"
    for manifest in shared:
        assert not manifest.capabilities, (
            f"{manifest.skill_id} is shared but declares capabilities, "
            "which would let the orchestrator schedule it directly"
        )


def test_artifact_skills_are_priced_as_heavy() -> None:
    """Guardrails cap heavy artifacts, so the cost model has to mark them."""

    by_id = {m.skill_id: m for m in discover(SKILLS_ROOT)}
    for name in ("lesson-intro", "interactive-lecture-deck", "interactive-visual-explainer"):
        assert by_id[name].cost["heavy_artifact"] is True, f"{name} should be priced as heavy"
    assert by_id["prerequisite-analyzer"].cost["heavy_artifact"] is False


def test_capability_vocabulary_is_closed() -> None:
    assert parse("teach.strategy") is Capability.TEACH_STRATEGY
    with pytest.raises(UnknownCapability):
        parse("teach.vibes")


def test_unknown_capability_tags_are_dropped_not_fatal() -> None:
    manifest = parse_manifest(
        "---\nname: x\nmetadata:\n  capabilities:\n    - teach.strategy\n"
        "    - not.a.capability\n  ownership: dedicated\n---\nbody\n",
        skill_id="x",
    )
    assert [str(c) for c in manifest.capabilities] == ["teach.strategy"]


def test_frontmatter_must_be_a_mapping() -> None:
    with pytest.raises(SkillManifestError):
        split_frontmatter("---\n- just\n- a\n- list\n---\nbody\n")


def test_manifest_without_frontmatter_still_yields_an_entry() -> None:
    manifest = parse_manifest("# no frontmatter\n", skill_id="plain")
    assert manifest.skill_id == "plain"
    assert manifest.capabilities == ()


@pytest.mark.asyncio
async def test_sync_seeds_the_registry_and_is_idempotent(state_db) -> None:
    _database, runtime, learner_id = state_db
    manifests = discover(SKILLS_ROOT)

    await runtime.sync_skill_manifests(manifests)
    first = await runtime.list_skills(learner_id=learner_id)
    assert len(first) == len(manifests)

    await runtime.sync_skill_manifests(manifests)
    second = await runtime.list_skills(learner_id=learner_id)
    assert len(second) == len(first)

    grader = next(item for item in second if item["skill_id"] == "deterministic-grader")
    assert grader["capabilities"] == ["assess.grade"]
    assert grader["provider"] == "deterministic_grader"
    assert grader["enabled"] is True
    assert grader["checksum"].startswith("sha256:")


@pytest.mark.asyncio
async def test_forged_skills_are_registered_disabled(state_db) -> None:
    """Enabling a forged skill is an irreversible act that needs confirmation."""

    _database, runtime, learner_id = state_db
    forged = parse_manifest(
        "---\nname: counterexample-generator\nmetadata:\n  version: 0.1.0\n"
        "  capabilities:\n    - teach.explain\n  ownership: dedicated\n"
        "  provider: adaptive_pedagogy\n---\nbody\n",
        skill_id="counterexample-generator",
        source="forged",
    )
    assert forged.enabled is False

    stored = await runtime.register_skill(forged, learner_id=learner_id)
    assert stored["enabled"] is False
    assert stored["source"] == "forged"
    assert stored["learner_id"] == learner_id

    enabled = await runtime.set_skill_enabled("counterexample-generator", True)
    assert enabled["enabled"] is True


@pytest.mark.asyncio
async def test_sync_does_not_clobber_personal_or_forged_entries(state_db) -> None:
    _database, runtime, learner_id = state_db
    forged = parse_manifest(
        "---\nname: interactive-lecture-deck\nmetadata:\n  version: 9.9.9\n"
        "  ownership: dedicated\n---\nbody\n",
        skill_id="interactive-lecture-deck",
        source="forged",
    )
    await runtime.register_skill(forged, learner_id=learner_id)
    await runtime.sync_skill_manifests(discover(SKILLS_ROOT))

    entries = {item["skill_id"]: item for item in await runtime.list_skills(learner_id=learner_id)}
    # The learner's own entry wins over the shipped manifest of the same name.
    assert entries["interactive-lecture-deck"]["version"] == "9.9.9"
    assert entries["interactive-lecture-deck"]["source"] == "forged"
