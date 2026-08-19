"""Capability → skill → provider binding: the pure resolver half of dispatch.

Given the registry view the orchestrator planned against, decide which skill
row — and therefore which provider — serves one capability right now.  The
resolver is pure: no provider invocation, no database access, no event
emission, so every branch (no candidate, ambiguous candidate, disabled skill,
unavailable provider, tie-breaking) is unit-testable in isolation.

Determinism is a hard requirement: ties break on skill id so the same state
always resolves the same way and the trace stays reproducible.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ..candidates import RegisteredSkill, candidate_id


class NoProvider(LookupError):
    """No enabled skill provides the capability the plan asked for."""


@dataclass(slots=True)
class Resolution:
    """Which skill and provider will serve one capability, decided just now."""

    capability: str
    skill_id: str
    provider: str
    cost: dict[str, Any] = field(default_factory=dict)
    status_line: str = ""
    candidate_id: str = ""
    display_name: str = ""
    skill_version: str = ""
    skill_checksum: str = ""


def resolve(
    capability: str,
    skills: Sequence[Mapping[str, Any]],
    *,
    selected_candidate_id: str = "",
    knowledge_point_id: str = "",
    provider_available: Callable[[str], bool] | None = None,
) -> Resolution:
    """Pick the cheapest enabled skill that provides ``capability``.

    Ties break on skill id so the same state always resolves the same way; a
    resolution that varies run to run would make the trace unreproducible.

    ``provider_available`` is an optional pure predicate — typically a lookup
    into the registered provider table.  When supplied, rows whose provider is
    unavailable are skipped, so a missing implementation falls back to the
    next eligible skill instead of producing a binding that cannot run.  The
    predicate itself is injected, keeping this function free of provider-side
    effects.
    """

    matches = []
    for row in skills:
        skill = RegisteredSkill.from_row(row)
        if not skill.enabled or not skill.provider or capability not in skill.capabilities:
            continue
        if provider_available is not None and not provider_available(skill.provider):
            continue
        if (
            selected_candidate_id
            and candidate_id(skill, capability, knowledge_point_id) == selected_candidate_id
        ):
            matches.append(row)
        elif not selected_candidate_id:
            matches.append(row)
    if not matches:
        suffix = f" bound candidate {selected_candidate_id}" if selected_candidate_id else ""
        raise NoProvider(f"no enabled skill provides {capability}{suffix}")
    if selected_candidate_id and len(matches) != 1:
        raise NoProvider(f"candidate binding is ambiguous: {selected_candidate_id}")
    matches.sort(
        key=lambda row: (
            float((row.get("cost") or {}).get("latency_weight") or 1.0),
            str(row.get("skill_id")),
        )
    )
    chosen = matches[0]
    metadata = chosen.get("metadata") or {}
    return Resolution(
        capability=capability,
        skill_id=str(chosen["skill_id"]),
        provider=str(chosen["provider"]),
        cost=dict(chosen.get("cost") or {}),
        status_line=str(metadata.get("status_line") or "正在处理这一步…"),
        candidate_id=selected_candidate_id,
        display_name=str(chosen.get("display_name") or ""),
        skill_version=str(chosen.get("version") or ""),
        skill_checksum=str(chosen.get("checksum") or ""),
    )


__all__ = ["NoProvider", "Resolution", "resolve"]
