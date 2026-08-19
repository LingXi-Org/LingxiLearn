"""Pure tests for the dispatch binding resolver (issue #60).

``runtime.dispatch.binding.resolve`` maps a capability to a skill row and its
provider.  It is pure — no provider side effect, no database, no events — so
every branch is exercised here with plain registry rows.
"""

from __future__ import annotations

import pytest

from lingxilearn.runtime.candidates import RegisteredSkill, candidate_id
from lingxilearn.runtime.dispatch.binding import NoProvider, resolve


def _row(
    skill_id: str,
    capability: str,
    provider: str,
    *,
    latency_weight: float = 1.0,
    enabled: bool = True,
    version: str = "1.0.0",
    checksum: str = "sha256:test",
    display_name: str = "",
    status_line: str = "",
) -> dict:
    row = {
        "skill_id": skill_id,
        "capabilities": [capability],
        "provider": provider,
        "cost": {"latency_weight": latency_weight},
        "preconditions": {},
        "enabled": enabled,
        "version": version,
        "checksum": checksum,
        "display_name": display_name,
    }
    if status_line:
        row["metadata"] = {"status_line": status_line}
    return row


def test_no_candidate_raises() -> None:
    with pytest.raises(NoProvider, match="no enabled skill provides"):
        resolve("dialog.answer", [])


def test_capability_mismatch_is_not_a_candidate() -> None:
    with pytest.raises(NoProvider):
        resolve("dialog.answer", [_row("deck-skill", "content.deck", "p_deck")])


def test_disabled_skill_is_not_resolvable() -> None:
    with pytest.raises(NoProvider):
        resolve("dialog.answer", [_row("off", "dialog.answer", "p_a", enabled=False)])


def test_skill_without_provider_is_not_resolvable() -> None:
    with pytest.raises(NoProvider):
        resolve("dialog.answer", [_row("empty", "dialog.answer", "")])


def test_cheapest_of_multiple_candidates_wins() -> None:
    skills = [
        _row("expensive", "assess.generate", "p_a", latency_weight=4.0),
        _row("cheap", "assess.generate", "p_b", latency_weight=1.0),
    ]
    assert resolve("assess.generate", skills).skill_id == "cheap"


def test_tie_breaks_deterministically_on_skill_id() -> None:
    skills = [
        _row("beta", "assess.generate", "p_b"),
        _row("alpha", "assess.generate", "p_a"),
    ]
    assert resolve("assess.generate", skills).skill_id == "alpha"
    assert resolve("assess.generate", list(reversed(skills))).skill_id == "alpha"


def test_resolution_carries_binding_metadata() -> None:
    row = _row(
        "qa",
        "dialog.answer",
        "p_qa",
        display_name="知识点答疑",
        version="2.1.0",
        checksum="sha256:cafe",
        status_line="正在检索资料…",
    )
    resolution = resolve("dialog.answer", [row])
    assert resolution.provider == "p_qa"
    assert resolution.display_name == "知识点答疑"
    assert resolution.skill_version == "2.1.0"
    assert resolution.skill_checksum == "sha256:cafe"
    assert resolution.status_line == "正在检索资料…"


def test_resolution_default_status_line() -> None:
    assert resolve("dialog.answer", [_row("qa", "dialog.answer", "p_qa")]).status_line


def test_selected_candidate_binds_exactly() -> None:
    chosen = _row("chosen", "content.visual", "p_chosen")
    other = _row("other", "content.visual", "p_other", latency_weight=0.1)
    bound = candidate_id(RegisteredSkill.from_row(chosen), "content.visual", "kp-1")
    resolution = resolve(
        "content.visual", [chosen, other], selected_candidate_id=bound, knowledge_point_id="kp-1"
    )
    assert resolution.skill_id == "chosen"
    assert resolution.candidate_id == bound


def test_unknown_selected_candidate_raises() -> None:
    with pytest.raises(NoProvider, match="bound candidate candidate_missing"):
        resolve(
            "content.visual",
            [_row("only", "content.visual", "p_a")],
            selected_candidate_id="candidate_missing",
            knowledge_point_id="kp-1",
        )


def test_ambiguous_candidate_binding_raises() -> None:
    row = _row("dup", "content.visual", "p_dup")
    bound = candidate_id(RegisteredSkill.from_row(row), "content.visual", "")
    with pytest.raises(NoProvider, match="candidate binding is ambiguous"):
        resolve("content.visual", [row, dict(row)], selected_candidate_id=bound)


def test_unavailable_provider_is_skipped_for_fallback() -> None:
    """The cheapest skill's provider is missing; the next eligible skill runs."""

    skills = [
        _row("cheapest", "content.visual", "p_missing", latency_weight=0.1),
        _row("fallback", "content.visual", "p_ready", latency_weight=9.0),
    ]
    resolution = resolve(
        "content.visual", skills, provider_available=lambda name: name != "p_missing"
    )
    assert resolution.skill_id == "fallback"
    assert resolution.provider == "p_ready"


def test_all_providers_unavailable_raises() -> None:
    skills = [_row("only", "content.visual", "p_missing")]
    with pytest.raises(NoProvider):
        resolve("content.visual", skills, provider_available=lambda name: False)


def test_bound_candidate_with_unavailable_provider_raises() -> None:
    chosen = _row("chosen", "content.visual", "p_missing")
    bound = candidate_id(RegisteredSkill.from_row(chosen), "content.visual", "")
    with pytest.raises(NoProvider, match="bound candidate"):
        resolve(
            "content.visual",
            [chosen],
            selected_candidate_id=bound,
            provider_available=lambda name: False,
        )


def test_resolution_is_pure() -> None:
    """Binding observes nothing but its inputs: repeated calls agree exactly."""

    skills = [_row("a", "content.visual", "p_a"), _row("b", "content.visual", "p_b")]
    first = resolve("content.visual", skills)
    second = resolve("content.visual", skills)
    assert first == second
