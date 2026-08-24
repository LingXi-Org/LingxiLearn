from __future__ import annotations

from typing import Any

from ..store.models.knowledge import KnowledgeBase
from ..store.workspace_knowledge_repository import WorkspaceKnowledgeRepository
from .workspace_errors import WorkspaceForbidden, WorkspaceResourceNotFound
from .workspace_files import safe_leaf_name


class WorkspaceKnowledgeService:
    """Application boundary for learner-owned knowledge resources."""

    def __init__(self, db: Any) -> None:
        self.repository = WorkspaceKnowledgeRepository(db)

    async def require_base(self, learner_id: str, base_id: str) -> KnowledgeBase:
        row = await self.repository.find_base(learner_id, base_id)
        if row is None:
            raise WorkspaceResourceNotFound("resource_not_found")
        return row

    async def update_document(
        self, base_id: str, document_id: str, body: dict[str, Any]
    ) -> Any:
        normalized = dict(body)
        if body.get("name") is not None or body.get("filename") is not None:
            normalized["name"] = safe_leaf_name(str(body.get("name") or body.get("filename")))
            normalized.pop("filename", None)
        row, read_only = await self.repository.update_document(base_id, document_id, normalized)
        if row is None:
            raise WorkspaceResourceNotFound("resource_not_found")
        if read_only:
            raise WorkspaceForbidden("read_only_document")
        return row
