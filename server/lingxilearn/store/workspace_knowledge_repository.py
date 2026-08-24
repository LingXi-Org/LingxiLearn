from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, false, func, select

from .models.knowledge import (
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentTag,
    KnowledgeTag,
)
from .models.workspace import WorkspaceUploadSession


class WorkspaceKnowledgeRepository:
    def __init__(self, db: Any) -> None:
        self._db = db

    async def list_bases(
        self, learner_id: str, scope: str, include_archived: bool
    ) -> list[tuple[KnowledgeBase, int]]:
        async with self._db.session() as session:
            query = select(KnowledgeBase).where(KnowledgeBase.learner_id == learner_id)
            if scope in {"active", "archived"}:
                query = query.where(KnowledgeBase.archived.is_(scope == "archived"))
            elif not include_archived:
                query = query.where(KnowledgeBase.archived.is_(False))
            rows = list(
                (await session.execute(query.order_by(KnowledgeBase.updated_at.desc())))
                .scalars()
                .all()
            )
            result = []
            for row in rows:
                count = await session.scalar(
                    select(func.count())
                    .select_from(KnowledgeDocument)
                    .where(
                        KnowledgeDocument.base_id == row.id,
                        KnowledgeDocument.archived.is_(False),
                    )
                )
                result.append((row, int(count or 0)))
            return result

    async def create_base(self, learner_id: str, name: str, description: str) -> KnowledgeBase:
        row = KnowledgeBase(
            id=f"kb_{uuid.uuid4().hex}",
            learner_id=learner_id,
            name=name,
            description=description,
            metadata_payload={},
        )
        async with self._db.session() as session:
            session.add(row)
            await session.commit()
            return row

    async def find_base(self, learner_id: str, base_id: str) -> KnowledgeBase | None:
        async with self._db.session() as session:
            return await session.scalar(
                select(KnowledgeBase).where(
                    KnowledgeBase.id == base_id, KnowledgeBase.learner_id == learner_id
                )
            )

    async def search_documents(self, learner_id: str) -> list[KnowledgeDocument]:
        async with self._db.session() as session:
            bases = list(
                (
                    await session.execute(
                        select(KnowledgeBase).where(
                            KnowledgeBase.learner_id == learner_id,
                            KnowledgeBase.archived.is_(False),
                        )
                    )
                )
                .scalars()
                .all()
            )
            base_ids = [row.id for row in bases]
            query = (
                select(KnowledgeDocument).where(
                    KnowledgeDocument.base_id.in_(base_ids),
                    KnowledgeDocument.archived.is_(False),
                )
                if base_ids
                else select(KnowledgeDocument).where(false())
            )
            return list((await session.execute(query)).scalars().all())

    async def update_base(self, base_id: str, body: dict[str, Any]) -> KnowledgeBase | None:
        async with self._db.session() as session:
            row = await session.get(KnowledgeBase, base_id)
            if row is None:
                return None
            if body.get("name") is not None:
                row.name = str(body["name"]).strip()[:255]
            if body.get("description") is not None:
                row.description = str(body["description"])
            await session.commit()
            return row

    async def set_base_archived(self, base_id: str, archived: bool) -> KnowledgeBase | None:
        async with self._db.session() as session:
            row = await session.get(KnowledgeBase, base_id)
            if row is not None:
                row.archived = archived
                await session.commit()
            return row

    async def list_documents(
        self, base_id: str, include_archived: bool, enabled_filter: str | None
    ) -> list[KnowledgeDocument]:
        async with self._db.session() as session:
            query = select(KnowledgeDocument).where(KnowledgeDocument.base_id == base_id)
            if not include_archived:
                query = query.where(KnowledgeDocument.archived.is_(False))
            if enabled_filter == "enabled":
                query = query.where(KnowledgeDocument.archived.is_(False))
            elif enabled_filter == "disabled":
                query = query.where(KnowledgeDocument.archived.is_(True))
            return list(
                (await session.execute(query.order_by(KnowledgeDocument.updated_at.desc())))
                .scalars()
                .all()
            )

    async def list_tags(self, base_id: str) -> list[KnowledgeTag]:
        async with self._db.session() as session:
            return list(
                (
                    await session.execute(
                        select(KnowledgeTag)
                        .where(KnowledgeTag.base_id == base_id)
                        .order_by(KnowledgeTag.name)
                    )
                )
                .scalars()
                .all()
            )

    async def tag_usage(
        self, base_id: str
    ) -> list[tuple[KnowledgeTag, list[tuple[KnowledgeDocument, Any]]]]:
        async with self._db.session() as session:
            tags = list(
                (
                    await session.execute(
                        select(KnowledgeTag)
                        .where(KnowledgeTag.base_id == base_id)
                        .order_by(KnowledgeTag.name)
                    )
                )
                .scalars()
                .all()
            )
            result = []
            for tag in tags:
                links = list(
                    (
                        await session.execute(
                            select(KnowledgeDocumentTag).where(
                                KnowledgeDocumentTag.tag_id == tag.id
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                documents = []
                for link in links:
                    document = await session.get(KnowledgeDocument, link.document_id)
                    if document is not None and not document.archived:
                        documents.append((document, link.value))
                result.append((tag, documents))
            return result

    async def create_tag(self, base_id: str, name: str, slot: str, field_type: str) -> KnowledgeTag:
        row = KnowledgeTag(
            id=f"tag_{uuid.uuid4().hex}",
            base_id=base_id,
            name=name[:128],
            tag_slot=slot,
            field_type=field_type,
        )
        async with self._db.session() as session:
            session.add(row)
            await session.commit()
            return row

    async def update_tag(
        self, base_id: str, tag_id: str, body: dict[str, Any]
    ) -> KnowledgeTag | None:
        async with self._db.session() as session:
            row = await session.scalar(
                select(KnowledgeTag).where(
                    KnowledgeTag.id == tag_id, KnowledgeTag.base_id == base_id
                )
            )
            if row is None:
                return None
            if body.get("name") is not None:
                row.name = str(body["name"]).strip()[:128]
            if body.get("fieldType") is not None:
                row.field_type = str(body["fieldType"])
            await session.commit()
            return row

    async def delete_tag(self, base_id: str, tag_id: str) -> bool:
        async with self._db.session() as session:
            row = await session.scalar(
                select(KnowledgeTag).where(
                    KnowledgeTag.id == tag_id, KnowledgeTag.base_id == base_id
                )
            )
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True

    async def document_exists(self, base_id: str, document_id: str) -> bool:
        async with self._db.session() as session:
            return (
                await session.scalar(
                    select(KnowledgeDocument).where(
                        KnowledgeDocument.id == document_id,
                        KnowledgeDocument.base_id == base_id,
                    )
                )
                is not None
            )

    async def save_tag_definitions(
        self, base_id: str, document_id: str, definitions: list[Any]
    ) -> tuple[list[KnowledgeTag], list[KnowledgeTag]] | None:
        async with self._db.session() as session:
            document = await session.scalar(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.id == document_id,
                    KnowledgeDocument.base_id == base_id,
                )
            )
            if document is None:
                return None
            created, updated = [], []
            for definition in definitions:
                if not isinstance(definition, dict):
                    continue
                slot = str(definition.get("tagSlot") or "").strip()
                name = str(definition.get("displayName") or "").strip()
                field_type = str(definition.get("fieldType") or "text").strip()
                if not slot or not name:
                    continue
                row = await session.scalar(
                    select(KnowledgeTag).where(
                        KnowledgeTag.base_id == base_id, KnowledgeTag.tag_slot == slot
                    )
                )
                if row is None:
                    row = KnowledgeTag(
                        id=f"tag_{uuid.uuid4().hex}",
                        base_id=base_id,
                        name=name[:128],
                        tag_slot=slot,
                        field_type=field_type,
                    )
                    session.add(row)
                    created.append(row)
                else:
                    row.name = name[:128]
                    row.field_type = field_type
                    updated.append(row)
            await session.commit()
            return created, updated

    async def delete_document_tags(self, base_id: str, document_id: str) -> bool:
        async with self._db.session() as session:
            document = await session.scalar(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.id == document_id,
                    KnowledgeDocument.base_id == base_id,
                )
            )
            if document is None:
                return False
            await session.execute(
                delete(KnowledgeDocumentTag).where(KnowledgeDocumentTag.document_id == document_id)
            )
            await session.commit()
            return True

    @staticmethod
    def _add_chunks(
        session: Any, document_id: str, content: str, *, enabled: bool | None = None
    ) -> None:
        metadata = {} if enabled is None else {"enabled": enabled}
        for ordinal, start in enumerate(range(0, len(content), 1200)):
            session.add(
                KnowledgeChunk(
                    id=f"chunk_{uuid.uuid4().hex}",
                    document_id=document_id,
                    ordinal=ordinal,
                    text=content[start : start + 1200],
                    metadata_payload=metadata,
                )
            )

    async def create_document(
        self,
        base_id: str,
        name: str,
        mime_type: str,
        content: str,
        metadata: dict[str, Any],
        *,
        enabled_chunks: bool | None = None,
        upload_id: str | None = None,
    ) -> KnowledgeDocument:
        row = KnowledgeDocument(
            id=f"doc_{uuid.uuid4().hex}",
            base_id=base_id,
            name=name,
            mime_type=mime_type,
            content=content,
            metadata_payload=metadata,
        )
        async with self._db.session() as session:
            session.add(row)
            self._add_chunks(session, row.id, content, enabled=enabled_chunks)
            if upload_id:
                upload = await session.get(WorkspaceUploadSession, upload_id)
                if upload is not None:
                    upload.status = "completed"
                    upload.file_id = row.id
            await session.commit()
            return row

    async def upsert_document(
        self, base_id: str, document_id: str, name: str, mime_type: str, content: str
    ) -> tuple[KnowledgeDocument, bool]:
        async with self._db.session() as session:
            row = (
                await session.scalar(
                    select(KnowledgeDocument).where(
                        KnowledgeDocument.id == document_id,
                        KnowledgeDocument.base_id == base_id,
                    )
                )
                if document_id
                else None
            )
            is_update = row is not None
            if row is None:
                row = KnowledgeDocument(
                    id=document_id or f"doc_{uuid.uuid4().hex}",
                    base_id=base_id,
                    name=name,
                    mime_type=mime_type,
                    content=content,
                    metadata_payload={},
                )
                session.add(row)
            else:
                row.name = name
                row.mime_type = mime_type
                row.content = content
                row.archived = False
                await session.execute(
                    delete(KnowledgeChunk).where(KnowledgeChunk.document_id == row.id)
                )
            self._add_chunks(session, row.id, content, enabled=True)
            await session.commit()
            return row, is_update

    async def bulk_documents(
        self, base_id: str, document_ids: set[str], operation: str
    ) -> list[KnowledgeDocument]:
        async with self._db.session() as session:
            rows = list(
                (
                    await session.execute(
                        select(KnowledgeDocument).where(
                            KnowledgeDocument.base_id == base_id,
                            KnowledgeDocument.id.in_(document_ids),
                        )
                    )
                )
                .scalars()
                .all()
            )
            for row in rows:
                row.archived = operation != "enable"
            await session.commit()
            return rows

    async def find_document(self, base_id: str, document_id: str) -> KnowledgeDocument | None:
        async with self._db.session() as session:
            return await session.scalar(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.id == document_id,
                    KnowledgeDocument.base_id == base_id,
                )
            )

    async def set_document_archived(
        self, base_id: str, document_id: str, archived: bool
    ) -> KnowledgeDocument | None:
        async with self._db.session() as session:
            row = await session.scalar(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.id == document_id,
                    KnowledgeDocument.base_id == base_id,
                )
            )
            if row is not None:
                row.archived = archived
                await session.commit()
            return row

    async def set_upload_status(
        self, upload_id: str, status: str, file_id: str | None = None
    ) -> None:
        async with self._db.session() as session:
            row = await session.get(WorkspaceUploadSession, upload_id)
            if row is not None:
                row.status = status
                if file_id is not None:
                    row.file_id = file_id
                await session.commit()

    async def document_chunks(
        self, base_id: str, document_id: str
    ) -> tuple[KnowledgeDocument, list[KnowledgeChunk]] | None:
        async with self._db.session() as session:
            document = await session.scalar(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.id == document_id,
                    KnowledgeDocument.base_id == base_id,
                )
            )
            if document is None:
                return None
            rows = list(
                (
                    await session.execute(
                        select(KnowledgeChunk)
                        .where(KnowledgeChunk.document_id == document_id)
                        .order_by(KnowledgeChunk.ordinal)
                    )
                )
                .scalars()
                .all()
            )
            return document, rows

    async def create_chunk(
        self, base_id: str, document_id: str, content: str, enabled: bool
    ) -> tuple[KnowledgeDocument, KnowledgeChunk] | None:
        async with self._db.session() as session:
            document = await session.scalar(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.id == document_id,
                    KnowledgeDocument.base_id == base_id,
                )
            )
            if document is None:
                return None
            ordinal = await session.scalar(
                select(func.max(KnowledgeChunk.ordinal)).where(
                    KnowledgeChunk.document_id == document_id
                )
            )
            row = KnowledgeChunk(
                id=f"chunk_{uuid.uuid4().hex}",
                document_id=document_id,
                ordinal=int(ordinal or -1) + 1,
                text=content,
                metadata_payload={"enabled": enabled},
            )
            session.add(row)
            await session.commit()
            return document, row

    async def find_chunk(
        self, base_id: str, document_id: str, chunk_id: str
    ) -> tuple[KnowledgeDocument, KnowledgeChunk] | None:
        async with self._db.session() as session:
            document = await session.scalar(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.id == document_id,
                    KnowledgeDocument.base_id == base_id,
                )
            )
            row = await session.scalar(
                select(KnowledgeChunk).where(
                    KnowledgeChunk.id == chunk_id,
                    KnowledgeChunk.document_id == document_id,
                )
            )
            return (document, row) if document is not None and row is not None else None

    async def update_chunk(
        self, base_id: str, document_id: str, chunk_id: str, body: dict[str, Any]
    ) -> tuple[KnowledgeDocument, KnowledgeChunk] | None:
        async with self._db.session() as session:
            result = await self._find_chunk_in_session(session, base_id, document_id, chunk_id)
            if result is None:
                return None
            document, row = result
            if body.get("content") is not None:
                row.text = str(body["content"])
            if body.get("enabled") is not None:
                row.metadata_payload = {
                    **(row.metadata_payload or {}),
                    "enabled": bool(body["enabled"]),
                }
            await session.commit()
            return document, row

    @staticmethod
    async def _find_chunk_in_session(
        session: Any, base_id: str, document_id: str, chunk_id: str
    ) -> tuple[KnowledgeDocument, KnowledgeChunk] | None:
        document = await session.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == document_id,
                KnowledgeDocument.base_id == base_id,
            )
        )
        row = await session.scalar(
            select(KnowledgeChunk).where(
                KnowledgeChunk.id == chunk_id,
                KnowledgeChunk.document_id == document_id,
            )
        )
        return (document, row) if document is not None and row is not None else None

    async def delete_chunk(self, base_id: str, document_id: str, chunk_id: str) -> bool:
        async with self._db.session() as session:
            document = await session.scalar(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.id == document_id,
                    KnowledgeDocument.base_id == base_id,
                )
            )
            if document is None:
                return False
            row = await session.scalar(
                select(KnowledgeChunk).where(
                    KnowledgeChunk.id == chunk_id,
                    KnowledgeChunk.document_id == document_id,
                )
            )
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True

    async def bulk_chunks(
        self, base_id: str, document_id: str, chunk_ids: set[str], operation: str
    ) -> list[KnowledgeChunk]:
        async with self._db.session() as session:
            document = await session.scalar(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.id == document_id,
                    KnowledgeDocument.base_id == base_id,
                )
            )
            if document is None:
                return []
            rows = list(
                (
                    await session.execute(
                        select(KnowledgeChunk).where(
                            KnowledgeChunk.document_id == document_id,
                            KnowledgeChunk.id.in_(chunk_ids),
                        )
                    )
                )
                .scalars()
                .all()
            )
            if operation == "delete":
                for row in rows:
                    await session.delete(row)
            else:
                for row in rows:
                    row.metadata_payload = {
                        **(row.metadata_payload or {}),
                        "enabled": operation == "enable",
                    }
            await session.commit()
            return rows

    async def update_document(
        self,
        base_id: str,
        document_id: str,
        body: dict[str, Any],
    ) -> tuple[KnowledgeDocument | None, bool]:
        async with self._db.session() as session:
            row = await session.scalar(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.id == document_id,
                    KnowledgeDocument.base_id == base_id,
                )
            )
            if row is None:
                return None, False
            if (row.metadata_payload or {}).get("readOnly") and any(
                key in body for key in ("name", "filename", "content", "enabled")
            ):
                return row, True
            if body.get("name") is not None or body.get("filename") is not None:
                row.name = str(body.get("name") or body.get("filename"))
            if isinstance(body.get("content"), str):
                row.content = body["content"]
                await session.execute(
                    delete(KnowledgeChunk).where(KnowledgeChunk.document_id == row.id)
                )
                self._add_chunks(session, row.id, row.content)
            if body.get("enabled") is not None:
                row.archived = not bool(body["enabled"])
            tag_keys = (
                {f"tag{index}" for index in range(1, 8)}
                | {f"number{index}" for index in range(1, 6)}
                | {"date1", "date2", "boolean1", "boolean2", "boolean3"}
            )
            if any(key in body for key in tag_keys):
                metadata = {**(row.metadata_payload or {})}
                for key in tag_keys:
                    if key in body:
                        metadata[key] = body[key] or None
                row.metadata_payload = metadata
                await self._sync_text_tag_links(session, row, base_id, body, tag_keys)
            await session.commit()
            return row, False

    @staticmethod
    async def _sync_text_tag_links(
        session: Any,
        document: KnowledgeDocument,
        base_id: str,
        body: dict[str, Any],
        tag_keys: set[str],
    ) -> None:
        for slot in [key for key in tag_keys if key.startswith("tag")]:
            if slot not in body:
                continue
            tag = await session.scalar(
                select(KnowledgeTag).where(
                    KnowledgeTag.base_id == base_id, KnowledgeTag.tag_slot == slot
                )
            )
            if tag is None:
                continue
            link = await session.scalar(
                select(KnowledgeDocumentTag).where(
                    KnowledgeDocumentTag.document_id == document.id,
                    KnowledgeDocumentTag.tag_id == tag.id,
                )
            )
            value = str(body.get(slot) or "")
            if value:
                if link is None:
                    session.add(
                        KnowledgeDocumentTag(document_id=document.id, tag_id=tag.id, value=value)
                    )
                else:
                    link.value = value
            elif link is not None:
                await session.delete(link)
