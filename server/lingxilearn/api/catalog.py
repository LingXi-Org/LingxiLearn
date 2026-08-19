"""Learning pack and skill catalogue endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from ..config import REPO_ROOT
from ..contracts.rest_models import (
    PacksResponse,
    SkillRegistryResponse,
    SkillsResponse,
)
from ..learner import LearnerContext
from ..state.capabilities import CAPABILITY_INFO
from ..store.models.workspace import PersonalSkill
from .dependencies import current_learner_context, services_of

router = APIRouter(prefix="/api")


@router.get("/packs", response_model=PacksResponse)
async def list_packs(request: Request) -> dict[str, Any]:
    services = services_of(request)
    return {
        "packs": [
            {
                "id": pack.id,
                "title": pack.title,
                "version": pack.version,
                "description": pack.description,
                "concepts": [
                    {"id": c.id, "title": c.title, "summary": c.summary, "requires": c.requires}
                    for c in pack.concepts.values()
                ],
                "missions": [
                    {
                        "id": m.id,
                        "title": m.title,
                        "subtitle": m.subtitle,
                        "summary": m.summary,
                        "why_not_chat": m.why_not_chat,
                        "concepts": list(m.concepts),
                        "estimated_minutes": m.estimated_minutes,
                        "steps": len(m.steps),
                    }
                    for m in pack.missions.values()
                ],
            }
            for pack in services.packs.values()
        ]
    }


@router.get("/skills", response_model=SkillsResponse)
async def list_skills(
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """Expose the native LingxiSkills catalogue to the workspace."""

    services = services_of(request)
    skills: list[dict[str, Any]] = []
    for entry in await services.learner_state.list_skills(learner_id=context.learner_id):
        manifest_path = REPO_ROOT / "skills" / entry["skill_id"] / "SKILL.md"
        skills.append(
            {
                "id": entry["skill_id"],
                "name": entry["skill_id"],
                "display_name": entry["display_name"] or entry["skill_id"],
                "description": entry["description"],
                "version": entry["version"],
                "license": "MIT",
                "compatibility": "",
                "content": manifest_path.read_text(encoding="utf-8")
                if manifest_path.is_file()
                else "",
                "source": entry["source"],
                "is_system": entry["source"] == "system",
                "capabilities": entry["capabilities"],
                "ownership": entry["ownership"],
                "provider": entry["provider"],
                "cost": entry["cost"],
                "enabled": entry["enabled"],
            }
        )
    async with services.db.session() as session:
        personal = (
            (
                await session.execute(
                    select(PersonalSkill).where(PersonalSkill.learner_id == context.learner_id)
                )
            )
            .scalars()
            .all()
        )
    skills.extend(
        {
            "id": row.id,
            "name": row.name,
            "display_name": row.name,
            "description": row.description,
            "content": row.content,
            "version": row.version,
            "source": "personal",
            "is_system": False,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in personal
    )
    return {"skills": skills}


@router.get("/skill-registry", response_model=SkillRegistryResponse)
async def skill_registry(
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """Expose the machine-readable capability registry used for planning."""

    services = services_of(request)
    entries = await services.learner_state.list_skills(learner_id=context.learner_id)
    by_capability: dict[str, list[str]] = {}
    for entry in entries:
        if not entry["enabled"]:
            continue
        for tag in entry["capabilities"]:
            by_capability.setdefault(tag, []).append(entry["skill_id"])
    return {
        "skills": entries,
        "capabilities": [
            {
                "capability": str(item.capability),
                "label": item.label,
                "learner_facing": item.learner_facing,
                "heavy_artifact": item.heavy_artifact,
                "irreversible": item.irreversible,
                "providers": by_capability.get(str(item.capability), []),
            }
            for item in CAPABILITY_INFO.values()
        ],
    }
