"""Read ``skills/*/SKILL.md`` into the capability registry.

The SKILL.md files already carry almost everything a registry needs — ``phase``,
``latency-class``, ``state-write-mode``, ``parallel-safe``, ``output-contract``.
This module parses that frontmatter with a real YAML loader and derives the two
things the runtime actually plans against: the **capability tags** a skill
provides and the **cost** of running it once.

Capability tags are declared explicitly under ``metadata.capabilities``.  A
skill without them still appears in the catalogue (so it stays visible in the
skills UI) but can never be selected by the orchestrator, which is the safe
direction to fail.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .capabilities import Capability, UnknownCapability, info, parse

logger = logging.getLogger(__name__)

_LATENCY_COST = {"interactive": 1.0, "background": 2.0, "offline": 4.0}
_HEAVY_EXECUTION_MODES = {"artifact-generation", "direct-editorial-html"}


class SkillManifestError(ValueError):
    """A SKILL.md could not be read as a manifest."""


@dataclass(frozen=True, slots=True)
class SkillManifest:
    """One skill, as the registry stores it."""

    skill_id: str
    source: str = "system"
    display_name: str = ""
    description: str = ""
    capabilities: tuple[Capability, ...] = ()
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    preconditions: dict[str, Any] = field(default_factory=dict)
    cost: dict[str, Any] = field(default_factory=dict)
    ownership: str = "dedicated"
    provider: str = ""
    status_line: str = ""
    version: str = ""
    enabled: bool = True
    checksum: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "source": self.source,
            "display_name": self.display_name,
            "description": self.description,
            "capabilities": [str(c) for c in self.capabilities],
            "input_schema": dict(self.input_schema),
            "output_schema": dict(self.output_schema),
            "preconditions": dict(self.preconditions),
            "cost": dict(self.cost),
            "ownership": self.ownership,
            "provider": self.provider,
            "version": self.version,
            "enabled": self.enabled,
            "checksum": self.checksum,
            "metadata_payload": dict(self.metadata) | {"status_line": self.status_line},
        }


def split_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    """Return the parsed YAML frontmatter and the remaining body."""

    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    try:
        loaded = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        raise SkillManifestError(f"invalid SKILL.md frontmatter: {exc}") from exc
    if not isinstance(loaded, dict):
        raise SkillManifestError("SKILL.md frontmatter must be a mapping")
    return loaded, parts[2]


def _capabilities(
    skill_id: str, metadata: dict[str, Any], *, shared: bool
) -> tuple[Capability, ...]:
    declared = metadata.get("capabilities") or []
    if isinstance(declared, str):
        declared = [item.strip() for item in declared.split(",") if item.strip()]
    resolved: list[Capability] = []
    for tag in declared:
        try:
            resolved.append(parse(str(tag)))
        except UnknownCapability:
            logger.warning("skill %s declares unknown capability %r; ignoring", skill_id, tag)
    if not resolved and not shared:
        # Shared skills are composed into providers rather than planned for, so
        # having no capability is correct for them and a mistake for the rest.
        logger.warning(
            "skill %s declares no capabilities; it will never be selected by the orchestrator",
            skill_id,
        )
    return tuple(dict.fromkeys(resolved))


def _cost(metadata: dict[str, Any], capabilities: tuple[Capability, ...]) -> dict[str, Any]:
    latency = str(metadata.get("latency-class") or "interactive")
    execution_mode = str(metadata.get("execution-mode") or "")
    heavy = any(info(c).heavy_artifact for c in capabilities) or any(
        mode in execution_mode for mode in _HEAVY_EXECUTION_MODES
    )
    blocking = str(metadata.get("blocking", "")).strip().casefold() != "false" and latency == (
        "interactive"
    )
    return {
        "latency_class": latency,
        "latency_weight": _LATENCY_COST.get(latency, 2.0),
        "heavy_artifact": bool(heavy),
        "blocking": bool(blocking),
        "parallel_safe": bool(metadata.get("parallel-safe", False)),
        "critical_path": str(metadata.get("critical-path", "true")).strip().casefold() != "false",
        "hop_budget": int(str(metadata.get("default-blocking-hop-budget") or 1) or 1),
    }


def _preconditions(metadata: dict[str, Any]) -> dict[str, Any]:
    explicit = metadata.get("preconditions")
    if isinstance(explicit, dict):
        return dict(explicit)
    return {
        "phase": str(metadata.get("phase") or ""),
        "state_write_mode": str(metadata.get("state-write-mode") or "none"),
        "requires": list(metadata.get("requires") or []),
    }


def parse_manifest(
    raw: str,
    *,
    skill_id: str,
    source: str = "system",
    provider: str = "",
) -> SkillManifest:
    """Turn one SKILL.md into a registry manifest."""

    frontmatter, body = split_frontmatter(raw)
    metadata = frontmatter.get("metadata")
    metadata = dict(metadata) if isinstance(metadata, dict) else {}
    name = str(frontmatter.get("name") or skill_id)
    ownership = str(
        metadata.get("ownership") or ("shared" if _is_shared(metadata) else "dedicated")
    )
    capabilities = _capabilities(name, metadata, shared=ownership == "shared")
    description = str(
        metadata.get("display-description") or frontmatter.get("description") or ""
    ).strip()
    declared_status = str(metadata.get("status-line") or "").strip()
    status_line = declared_status or (
        f"正在{info(capabilities[0]).label}…" if capabilities else "正在处理你的学习任务…"
    )

    return SkillManifest(
        skill_id=name,
        source=source,
        display_name=str(metadata.get("display-name") or name),
        description=description,
        capabilities=capabilities,
        input_schema={"contract": str(metadata.get("input-contract") or "")},
        output_schema={"contract": str(metadata.get("output-contract") or "")},
        preconditions=_preconditions(metadata),
        cost=_cost(metadata, capabilities),
        ownership=ownership,
        provider=provider or str(metadata.get("provider") or ""),
        status_line=status_line,
        version=str(metadata.get("version") or ""),
        enabled=source != "forged",
        checksum="sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32],
        metadata=metadata | {"body_chars": len(body)},
    )


def _is_shared(metadata: dict[str, Any]) -> bool:
    """Shared skills are the cross-cutting ones every agent may load."""

    return str(metadata.get("phase") or "") in {"shared", "runtime"}


def discover(root: Path, *, provider_for: dict[str, str] | None = None) -> list[SkillManifest]:
    """Read every ``<root>/<skill>/SKILL.md`` into a manifest."""

    providers = provider_for or {}
    manifests: list[SkillManifest] = []
    if not root.is_dir():
        return manifests
    for directory in sorted(item for item in root.iterdir() if item.is_dir()):
        manifest_path = directory / "SKILL.md"
        if not manifest_path.is_file():
            continue
        raw = manifest_path.read_text(encoding="utf-8")
        try:
            manifests.append(
                parse_manifest(
                    raw,
                    skill_id=directory.name,
                    source="system",
                    provider=providers.get(directory.name, ""),
                )
            )
        except SkillManifestError:
            logger.exception("skipping unreadable skill manifest: %s", manifest_path)
    return manifests


__all__ = [
    "SkillManifest",
    "SkillManifestError",
    "discover",
    "parse_manifest",
    "split_frontmatter",
]
