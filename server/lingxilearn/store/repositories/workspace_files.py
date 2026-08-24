from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from ..models.workspace import WorkspaceFile, WorkspaceFolder, WorkspaceUploadSession


def descendant_folder_ids(folders: list[WorkspaceFolder], roots: set[str]) -> set[str]:
    result = set(roots)
    changed = True
    while changed:
        changed = False
        for folder in folders:
            if folder.id not in result and folder.parent_id in result:
                result.add(folder.id)
                changed = True
    return result


class WorkspaceFileRepository:
    def __init__(self, db: Any) -> None:
        self._db = db

    async def list_folders(
        self, workspace_id: str, scope: str | None = None
    ) -> list[WorkspaceFolder]:
        async with self._db.session() as session:
            query = select(WorkspaceFolder).where(WorkspaceFolder.workspace_id == workspace_id)
            if scope in {"active", "archived"}:
                query = query.where(WorkspaceFolder.archived.is_(scope == "archived"))
            rows = await session.execute(query.order_by(WorkspaceFolder.created_at))
            return list(rows.scalars().all())

    async def get_folder(self, workspace_id: str, folder_id: str) -> WorkspaceFolder | None:
        async with self._db.session() as session:
            return await session.scalar(
                select(WorkspaceFolder).where(
                    WorkspaceFolder.id == folder_id, WorkspaceFolder.workspace_id == workspace_id
                )
            )

    async def add_folder(self, folder: WorkspaceFolder) -> WorkspaceFolder:
        async with self._db.session() as session:
            session.add(folder)
            await session.commit()
            return folder

    async def update_folder(
        self,
        workspace_id: str,
        folder_id: str,
        *,
        name: str | None,
        parent_id: str | None,
        set_parent: bool,
    ) -> WorkspaceFolder | None:
        async with self._db.session() as session:
            folder = await session.scalar(
                select(WorkspaceFolder).where(
                    WorkspaceFolder.id == folder_id, WorkspaceFolder.workspace_id == workspace_id
                )
            )
            if folder is None:
                return None
            if name is not None:
                folder.name = name
            if set_parent:
                folder.parent_id = parent_id
            await session.commit()
            return folder

    async def folder_tree_records(
        self, workspace_id: str
    ) -> tuple[list[WorkspaceFolder], list[WorkspaceFile]]:
        async with self._db.session() as session:
            folders = list(
                (
                    await session.execute(
                        select(WorkspaceFolder).where(WorkspaceFolder.workspace_id == workspace_id)
                    )
                )
                .scalars()
                .all()
            )
            files = list(
                (
                    await session.execute(
                        select(WorkspaceFile).where(WorkspaceFile.workspace_id == workspace_id)
                    )
                )
                .scalars()
                .all()
            )
            return folders, files

    async def archive_tree(self, workspace_id: str, roots: set[str]) -> tuple[int, int]:
        async with self._db.session() as session:
            folders = list(
                (
                    await session.execute(
                        select(WorkspaceFolder).where(WorkspaceFolder.workspace_id == workspace_id)
                    )
                )
                .scalars()
                .all()
            )
            files = list(
                (
                    await session.execute(
                        select(WorkspaceFile).where(WorkspaceFile.workspace_id == workspace_id)
                    )
                )
                .scalars()
                .all()
            )
            ids = descendant_folder_ids(folders, roots)
            folder_count = 0
            file_count = 0
            for row in folders:
                if row.id in ids:
                    if not row.archived:
                        folder_count += 1
                    row.archived = True
            for row in files:
                if row.folder_id in ids:
                    if not row.archived:
                        file_count += 1
                    row.archived = True
            await session.commit()
            return folder_count, file_count

    async def move_items(
        self, workspace_id: str, file_ids: set[str], folder_ids: set[str], target_id: str | None
    ) -> bool | None:
        async with self._db.session() as session:
            folders = list(
                (
                    await session.execute(
                        select(WorkspaceFolder).where(WorkspaceFolder.workspace_id == workspace_id)
                    )
                )
                .scalars()
                .all()
            )
            files = list(
                (
                    await session.execute(
                        select(WorkspaceFile).where(WorkspaceFile.workspace_id == workspace_id)
                    )
                )
                .scalars()
                .all()
            )
            folder_map = {row.id: row for row in folders}
            if target_id is not None and (
                target_id not in folder_map or folder_map[target_id].archived
            ):
                return None
            if file_ids - {row.id for row in files} or folder_ids - set(folder_map):
                return None
            if target_id in descendant_folder_ids(folders, folder_ids):
                return False
            for row in files:
                if row.id in file_ids:
                    row.folder_id = target_id
            for row in folders:
                if row.id in folder_ids:
                    row.parent_id = target_id
            await session.commit()
            return True

    async def bulk_archive(
        self, workspace_id: str, file_ids: set[str], root_folder_ids: set[str]
    ) -> tuple[int, int] | None:
        async with self._db.session() as session:
            folders = list(
                (
                    await session.execute(
                        select(WorkspaceFolder).where(WorkspaceFolder.workspace_id == workspace_id)
                    )
                )
                .scalars()
                .all()
            )
            files = list(
                (
                    await session.execute(
                        select(WorkspaceFile).where(WorkspaceFile.workspace_id == workspace_id)
                    )
                )
                .scalars()
                .all()
            )
            ids = descendant_folder_ids(folders, root_folder_ids)
            if root_folder_ids - {row.id for row in folders} or file_ids - {
                row.id for row in files
            }:
                return None
            archived_files = 0
            archived_folders = 0
            for row in files:
                if row.id in file_ids or row.folder_id in ids:
                    archived_files += int(not row.archived)
                    row.archived = True
            for row in folders:
                if row.id in ids:
                    archived_folders += int(not row.archived)
                    row.archived = True
            await session.commit()
            return archived_folders, archived_files

    async def restore_tree(
        self, workspace_id: str, folder_id: str
    ) -> tuple[WorkspaceFolder, int, int] | None:
        async with self._db.session() as session:
            folders = list(
                (
                    await session.execute(
                        select(WorkspaceFolder).where(WorkspaceFolder.workspace_id == workspace_id)
                    )
                )
                .scalars()
                .all()
            )
            root = next((row for row in folders if row.id == folder_id), None)
            if root is None:
                return None
            ids = descendant_folder_ids(folders, {folder_id})
            files = list(
                (
                    await session.execute(
                        select(WorkspaceFile).where(WorkspaceFile.workspace_id == workspace_id)
                    )
                )
                .scalars()
                .all()
            )
            restored_files = 0
            for row in folders:
                if row.id in ids:
                    row.archived = False
            for row in files:
                if row.folder_id in ids and row.archived:
                    row.archived = False
                    restored_files += 1
            await session.commit()
            return root, len(ids), restored_files

    async def list_files(
        self, workspace_id: str, scope: str | None = None, folder_id: str | None = None
    ) -> list[WorkspaceFile]:
        async with self._db.session() as session:
            query = select(WorkspaceFile).where(WorkspaceFile.workspace_id == workspace_id)
            if scope in {"active", "archived"}:
                query = query.where(WorkspaceFile.archived.is_(scope == "archived"))
            if folder_id is not None:
                query = query.where(WorkspaceFile.folder_id == folder_id)
            rows = await session.execute(query.order_by(WorkspaceFile.updated_at.desc()))
            return list(rows.scalars().all())

    async def get_file(self, workspace_id: str, file_id: str) -> WorkspaceFile | None:
        async with self._db.session() as session:
            return await session.scalar(
                select(WorkspaceFile).where(
                    WorkspaceFile.id == file_id, WorkspaceFile.workspace_id == workspace_id
                )
            )

    async def get_file_by_storage_key(
        self, workspace_id: str, storage_key: str
    ) -> WorkspaceFile | None:
        async with self._db.session() as session:
            return await session.scalar(
                select(WorkspaceFile).where(
                    WorkspaceFile.storage_key == storage_key,
                    WorkspaceFile.workspace_id == workspace_id,
                )
            )

    async def add_file(self, row: WorkspaceFile) -> WorkspaceFile:
        async with self._db.session() as session:
            session.add(row)
            await session.commit()
            return row

    async def save_file(self, row: WorkspaceFile) -> WorkspaceFile | None:
        async with self._db.session() as session:
            current = await session.get(WorkspaceFile, row.id)
            if current is None:
                return None
            for attr in (
                "name",
                "path",
                "folder_id",
                "width",
                "height",
                "archived",
                "size",
                "storage_key",
                "mime_type",
                "metadata_payload",
            ):
                setattr(current, attr, getattr(row, attr))
            await session.commit()
            return current

    async def usage(self, workspace_id: str) -> int:
        async with self._db.session() as session:
            return int(
                await session.scalar(
                    select(func.coalesce(func.sum(WorkspaceFile.size), 0)).where(
                        WorkspaceFile.workspace_id == workspace_id,
                        WorkspaceFile.archived.is_(False),
                    )
                )
                or 0
            )

    async def add_upload(self, row: WorkspaceUploadSession) -> None:
        async with self._db.session() as session:
            session.add(row)
            await session.commit()

    async def set_upload_status(self, upload_id: str, status: str) -> WorkspaceUploadSession | None:
        async with self._db.session() as session:
            row = await session.get(WorkspaceUploadSession, upload_id)
            if row is not None:
                row.status = status
                await session.commit()
            return row

    async def complete_upload(self, upload_id: str, file: WorkspaceFile) -> WorkspaceFile:
        async with self._db.session() as session:
            session.add(file)
            upload = await session.get(WorkspaceUploadSession, upload_id)
            if upload is not None:
                upload.status = "completed"
                upload.file_id = file.id
            await session.commit()
            return file
