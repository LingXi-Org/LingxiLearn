from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from ..store.models.workspace import WorkspaceFile, WorkspaceFolder, WorkspaceUploadSession
from ..store.repositories.workspace_files import WorkspaceFileRepository
from .workspace_errors import WorkspaceDomainError, WorkspaceResourceNotFound
from .workspace_files import safe_leaf_name


class WorkspaceFileService:
    def __init__(self, db: Any) -> None:
        self.repository = WorkspaceFileRepository(db)

    async def create_folder(self, workspace_id: str, body: dict[str, Any]) -> WorkspaceFolder:
        parent_id = body.get("parentId") or None
        if parent_id and await self.repository.get_folder(workspace_id, str(parent_id)) is None:
            raise WorkspaceResourceNotFound("resource_not_found")
        return await self.repository.add_folder(
            WorkspaceFolder(
                id=f"folder_{uuid.uuid4().hex}",
                workspace_id=workspace_id,
                parent_id=parent_id,
                name=safe_leaf_name(str(body.get("name") or "新文件夹")),
            )
        )

    async def update_folder(
        self, workspace_id: str, folder_id: str, body: dict[str, Any]
    ) -> WorkspaceFolder:
        name = safe_leaf_name(str(body["name"])) if "name" in body else None
        set_parent = "parentId" in body
        parent_id = body.get("parentId") or None
        if parent_id:
            parent = await self.repository.get_folder(workspace_id, str(parent_id))
            if parent is None or parent.id == folder_id:
                raise WorkspaceResourceNotFound("resource_not_found")
        row = await self.repository.update_folder(
            workspace_id,
            folder_id,
            name=name,
            parent_id=parent_id,
            set_parent=set_parent,
        )
        if row is None:
            raise WorkspaceResourceNotFound("resource_not_found")
        return row

    async def archive_folder(self, workspace_id: str, folder_id: str) -> tuple[int, int]:
        if await self.repository.get_folder(workspace_id, folder_id) is None:
            raise WorkspaceResourceNotFound("resource_not_found")
        return await self.repository.archive_tree(workspace_id, {folder_id})

    async def move_items(self, workspace_id: str, body: dict[str, Any]) -> tuple[int, int]:
        file_ids = {str(item) for item in body.get("fileIds") or []}
        folder_ids = {str(item) for item in body.get("folderIds") or []}
        outcome = await self.repository.move_items(
            workspace_id, file_ids, folder_ids, body.get("targetFolderId") or None
        )
        if outcome is None:
            raise WorkspaceResourceNotFound("resource_not_found")
        if outcome is False:
            raise WorkspaceDomainError("folder_cycle")
        return len(file_ids), len(folder_ids)

    async def bulk_archive(self, workspace_id: str, body: dict[str, Any]) -> tuple[int, int]:
        outcome = await self.repository.bulk_archive(
            workspace_id,
            {str(item) for item in body.get("fileIds") or []},
            {str(item) for item in body.get("folderIds") or []},
        )
        if outcome is None:
            raise WorkspaceResourceNotFound("resource_not_found")
        return outcome

    async def restore_folder(
        self, workspace_id: str, folder_id: str
    ) -> tuple[WorkspaceFolder, int, int]:
        outcome = await self.repository.restore_tree(workspace_id, folder_id)
        if outcome is None:
            raise WorkspaceResourceNotFound("resource_not_found")
        return outcome

    async def require_file(self, workspace_id: str, file_id: str) -> WorkspaceFile:
        row = await self.repository.get_file(workspace_id, file_id)
        if row is None:
            raise WorkspaceResourceNotFound("resource_not_found")
        return row

    async def create_file(
        self,
        *,
        workspace_id: str,
        folder_id: str | None,
        name: str,
        mime_type: str,
        size: int,
        storage_key: str,
        metadata: dict[str, Any] | None = None,
    ) -> WorkspaceFile:
        if folder_id:
            folder = await self.repository.get_folder(workspace_id, folder_id)
            if folder is None or folder.archived:
                raise WorkspaceResourceNotFound("resource_not_found")
        return await self.repository.add_file(
            WorkspaceFile(
                id=f"file_{uuid.uuid4().hex}",
                workspace_id=workspace_id,
                folder_id=folder_id,
                name=name,
                mime_type=mime_type,
                size=size,
                storage_key=storage_key,
                path=name,
                metadata_payload=metadata or {},
            )
        )

    async def create_upload(
        self,
        *,
        upload_id: str,
        workspace_id: str,
        learner_id: str,
        token_hash: str,
        name: str,
        mime_type: str,
        size: int,
        temp_key: str,
        expires_at: datetime,
    ) -> None:
        await self.repository.add_upload(
            WorkspaceUploadSession(
                id=upload_id,
                workspace_id=workspace_id,
                learner_id=learner_id,
                token_hash=token_hash,
                name=name,
                mime_type=mime_type,
                size=size,
                temp_key=temp_key,
                status="uploading",
                expires_at=expires_at,
            )
        )

    async def complete_upload(
        self,
        upload_id: str,
        **file_fields: Any,
    ) -> WorkspaceFile:
        workspace_id = str(file_fields["workspace_id"])
        folder_id = file_fields.get("folder_id")
        if folder_id:
            folder = await self.repository.get_folder(workspace_id, str(folder_id))
            if folder is None or folder.archived:
                raise WorkspaceResourceNotFound("resource_not_found")
        row = WorkspaceFile(id=f"file_{uuid.uuid4().hex}", **file_fields)
        return await self.repository.complete_upload(upload_id, row)
