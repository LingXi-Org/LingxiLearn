"""Workspace API routes split by resource family."""

from fastapi import APIRouter

from ..application.uploads import multipart_part_urls
from ..application.workspace_errors import WorkspaceDomainError
from .workspace_file_routes import _upload_sessions
from .workspace_route_shared import (
    MAX_FILE_SIZE,
    UTC,
    Any,
    Depends,
    DocumentTagSaveResponse,
    HTTPException,
    KnowledgeBase,
    KnowledgeBaseResponse,
    KnowledgeBasesResponse,
    KnowledgeBulkChunksResponse,
    KnowledgeBulkDocumentsResponse,
    KnowledgeChunk,
    KnowledgeChunkResponse,
    KnowledgeChunksResponse,
    KnowledgeDocument,
    KnowledgeDocumentResponse,
    KnowledgeDocumentsResponse,
    KnowledgeDocumentTag,
    KnowledgeDocumentUpsertResponse,
    KnowledgeMessageResponse,
    KnowledgeNextSlotResponse,
    KnowledgeSearchResponse,
    KnowledgeTag,
    KnowledgeTagListResponse,
    KnowledgeTagResponse,
    KnowledgeTagsResponse,
    KnowledgeTagUsageResponse,
    KnowledgeUploadCreateResponse,
    LearnerContext,
    Request,
    SuccessResponse,
    UploadStateResponse,
    WorkspaceUploadSession,
    _chunk_public,
    _document_public,
    _knowledge_base_public,
    _knowledge_upload_session_public,
    _mime_type,
    _parse_knowledge_document,
    _public_origin,
    _safe_name,
    _storage_root,
    _tag_public,
    _workspace_for_id,
    base64,
    current_learner_context,
    datetime,
    delete,
    false,
    func,
    hashlib,
    not_found,
    secrets,
    select,
    services_of,
    timedelta,
    utcnow,
    uuid,
)

router = APIRouter(prefix="/api")


@router.get("/knowledge", response_model=KnowledgeBasesResponse)
async def list_knowledge(
    request: Request,
    includeArchived: bool = False,
    scope: str = "active",
    workspaceId: str | None = None,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await services_of(request).artifacts.project_agent_artifacts(context.learner_id)
    async with services_of(request).db.session() as session:
        query = select(KnowledgeBase).where(KnowledgeBase.learner_id == context.learner_id)
        if scope in {"active", "archived"}:
            query = query.where(KnowledgeBase.archived.is_(scope == "archived"))
        elif not includeArchived:
            query = query.where(KnowledgeBase.archived.is_(False))
        rows = (
            (await session.execute(query.order_by(KnowledgeBase.updated_at.desc()))).scalars().all()
        )
        result = []
        for row in rows:
            count = (
                await session.scalar(
                    select(func.count())
                    .select_from(KnowledgeDocument)
                    .where(
                        KnowledgeDocument.base_id == row.id, KnowledgeDocument.archived.is_(False)
                    )
                )
                or 0
            )
            result.append(_knowledge_base_public(row, int(count)))
    return {"success": True, "data": result, "knowledgeBases": result}


@router.post("/knowledge", response_model=KnowledgeBaseResponse)
async def create_knowledge(
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    row = KnowledgeBase(
        id=f"kb_{uuid.uuid4().hex}",
        learner_id=context.learner_id,
        name=str(body.get("name") or "知识库"),
        description=str(body.get("description") or ""),
        metadata_payload={},
    )
    async with services_of(request).db.session() as session:
        session.add(row)
        await session.commit()
    public = _knowledge_base_public(row)
    return {"success": True, "data": public, "knowledgeBase": public}


async def _base_for_id(request: Request, base_id: str, context: LearnerContext) -> KnowledgeBase:
    async with services_of(request).db.session() as session:
        row = await session.scalar(
            select(KnowledgeBase).where(
                KnowledgeBase.id == base_id, KnowledgeBase.learner_id == context.learner_id
            )
        )
    if row is None:
        raise not_found()
    return row


@router.get("/knowledge/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    request: Request,
    q: str = "",
    limit: int = 20,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """Search before the ``/{base_id}`` route so ``search`` is not a base id."""

    needle = q.strip().casefold()
    async with services_of(request).db.session() as session:
        bases = (
            (
                await session.execute(
                    select(KnowledgeBase).where(
                        KnowledgeBase.learner_id == context.learner_id,
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
        docs = (await session.execute(query)).scalars().all()
    matches = []
    for doc in docs:
        haystack = f"{doc.name}\n{doc.content}".casefold()
        if not needle or needle in haystack:
            index = haystack.find(needle) if needle else 0
            matches.append(
                {
                    "document": _document_public(doc),
                    "score": 1.0 if needle and index >= 0 else 0.0,
                    "snippet": doc.content[max(0, index - 120) : index + 480],
                }
            )
    bounded = matches[: max(1, min(limit, 100))]
    return {"success": True, "data": bounded, "results": bounded}


@router.get("/knowledge/{base_id}/next-available-slot", response_model=KnowledgeNextSlotResponse)
async def next_available_tag_slot(
    base_id: str,
    request: Request,
    fieldType: str,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    prefix = {"text": "tag", "number": "number", "date": "date", "boolean": "boolean"}.get(
        fieldType, "tag"
    )
    async with services_of(request).db.session() as session:
        rows = (
            (await session.execute(select(KnowledgeTag).where(KnowledgeTag.base_id == base_id)))
            .scalars()
            .all()
        )
    used = [row.tag_slot for row in rows if row.tag_slot]
    for index in range(1, 8 if prefix == "tag" else 6):
        candidate = f"{prefix}{index}"
        if candidate not in used:
            return {
                "success": True,
                "data": {
                    "nextAvailableSlot": candidate,
                    "fieldType": fieldType,
                    "usedSlots": used,
                    "totalSlots": 7 if prefix == "tag" else 5,
                    "availableSlots": max(0, (7 if prefix == "tag" else 5) - len(used)),
                },
            }
    return {
        "success": True,
        "data": {
            "nextAvailableSlot": None,
            "fieldType": fieldType,
            "usedSlots": used,
            "totalSlots": 7 if prefix == "tag" else 5,
            "availableSlots": 0,
        },
    }


@router.get("/knowledge/{base_id}/tag-usage", response_model=KnowledgeTagUsageResponse)
async def tag_usage(
    base_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with services_of(request).db.session() as session:
        tags = (
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
        usages: list[dict[str, Any]] = []
        for tag in tags:
            links = (
                (
                    await session.execute(
                        select(KnowledgeDocumentTag).where(KnowledgeDocumentTag.tag_id == tag.id)
                    )
                )
                .scalars()
                .all()
            )
            documents: list[dict[str, Any]] = []
            for link in links:
                document = await session.get(KnowledgeDocument, link.document_id)
                if document is not None and not document.archived:
                    documents.append(
                        {"id": document.id, "name": document.name, "tagValue": link.value}
                    )
            public = _tag_public(tag)
            usages.append(
                {
                    "tagName": public["displayName"],
                    "tagSlot": public["tagSlot"],
                    "documentCount": len(documents),
                    "documents": documents,
                }
            )
    return {"success": True, "data": usages}


@router.get("/knowledge/{base_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge(
    base_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    row = await _base_for_id(request, base_id, context)
    public = _knowledge_base_public(row)
    return {"success": True, "data": public, "knowledgeBase": public}


@router.put("/knowledge/{base_id}", response_model=KnowledgeBaseResponse)
@router.patch("/knowledge/{base_id}", response_model=KnowledgeBaseResponse)
async def update_knowledge(
    base_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    row = await _base_for_id(request, base_id, context)
    async with services_of(request).db.session() as session:
        current = await session.get(KnowledgeBase, row.id)
        if current is None:
            raise not_found()
        if body.get("name") is not None:
            current.name = str(body["name"]).strip()[:255]
        if body.get("description") is not None:
            current.description = str(body["description"])
        await session.commit()
        row = current
    public = _knowledge_base_public(row)
    return {"success": True, "data": public, "knowledgeBase": public}


@router.delete("/knowledge/{base_id}", response_model=KnowledgeMessageResponse)
async def archive_knowledge(
    base_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    row = await _base_for_id(request, base_id, context)
    async with services_of(request).db.session() as session:
        current = await session.get(KnowledgeBase, row.id)
        if current is not None:
            current.archived = True
            await session.commit()
    return {"success": True, "data": {"message": "archived"}}


@router.post("/knowledge/{base_id}/restore", response_model=KnowledgeBaseResponse)
async def restore_knowledge(
    base_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    row = await _base_for_id(request, base_id, context)
    async with services_of(request).db.session() as session:
        current = await session.get(KnowledgeBase, row.id)
        if current is not None:
            current.archived = False
            await session.commit()
    public = _knowledge_base_public(row)
    return {"success": True, "data": public, "knowledgeBase": public}


@router.get("/knowledge/{base_id}/documents", response_model=KnowledgeDocumentsResponse)
async def list_documents(
    base_id: str,
    request: Request,
    includeArchived: bool = False,
    search: str | None = None,
    enabledFilter: str | None = None,
    sortBy: str | None = None,
    sortOrder: str | None = None,
    limit: int = 50,
    offset: int = 0,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with services_of(request).db.session() as session:
        query = select(KnowledgeDocument).where(KnowledgeDocument.base_id == base_id)
        if not includeArchived:
            query = query.where(KnowledgeDocument.archived.is_(False))
        if enabledFilter == "enabled":
            query = query.where(KnowledgeDocument.archived.is_(False))
        elif enabledFilter == "disabled":
            query = query.where(KnowledgeDocument.archived.is_(True))
        rows = (
            (await session.execute(query.order_by(KnowledgeDocument.updated_at.desc())))
            .scalars()
            .all()
        )
    if search:
        needle = search.casefold()
        rows = [row for row in rows if needle in f"{row.name}\n{row.content}".casefold()]
    if sortBy in {
        "filename",
        "fileSize",
        "tokenCount",
        "chunkCount",
        "uploadedAt",
        "processingStatus",
        "enabled",
    }:

        def sort_key(row: KnowledgeDocument) -> Any:
            values = {
                "filename": row.name,
                "fileSize": len(row.content.encode("utf-8")),
                "tokenCount": len(row.content) // 4,
                "chunkCount": max(1, (len(row.content) + 1199) // 1200) if row.content else 0,
                "uploadedAt": row.created_at or utcnow(),
                "processingStatus": "completed",
                "enabled": not row.archived,
            }
            return values[sortBy]

        rows = sorted(rows, key=sort_key, reverse=sortOrder == "desc")
    total = len(rows)
    rows = rows[max(0, offset) : max(0, offset) + min(100, max(1, limit))]
    result = [_document_public(row) for row in rows]
    return {
        "success": True,
        "data": {
            "documents": result,
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "hasMore": offset + len(result) < total,
            },
        },
        "documents": result,
    }


@router.get("/knowledge/{base_id}/tag-definitions", response_model=KnowledgeTagsResponse)
async def list_tag_definitions(
    base_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with services_of(request).db.session() as session:
        rows = (
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
    tags = [_tag_public(row) for row in rows]
    return {"success": True, "data": tags, "tags": tags}


@router.post(
    "/knowledge/{base_id}/tag-definitions", status_code=201, response_model=KnowledgeTagResponse
)
async def create_tag_definition(
    base_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    name = str(body.get("displayName") or body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="tag_name_required")
    field_type = str(body.get("fieldType") or body.get("field_type") or "text")
    row = KnowledgeTag(
        id=f"tag_{uuid.uuid4().hex}",
        base_id=base_id,
        name=name[:128],
        tag_slot=str(body.get("tagSlot") or ""),
        field_type=field_type,
    )
    async with services_of(request).db.session() as session:
        session.add(row)
        await session.commit()
    return {"success": True, "data": _tag_public(row)}


@router.patch("/knowledge/{base_id}/tag-definitions/{tag_id}", response_model=KnowledgeTagResponse)
async def update_tag_definition(
    base_id: str,
    tag_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with services_of(request).db.session() as session:
        row = await session.scalar(
            select(KnowledgeTag).where(KnowledgeTag.id == tag_id, KnowledgeTag.base_id == base_id)
        )
        if row is None:
            raise not_found()
        if body.get("name") is not None:
            row.name = str(body["name"]).strip()[:128]
        if body.get("fieldType") is not None:
            row.field_type = str(body["fieldType"])
        await session.commit()
    return {"success": True, "data": _tag_public(row)}


@router.delete("/knowledge/{base_id}/tag-definitions/{tag_id}", response_model=SuccessResponse)
async def delete_tag_definition(
    base_id: str,
    tag_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with services_of(request).db.session() as session:
        row = await session.scalar(
            select(KnowledgeTag).where(KnowledgeTag.id == tag_id, KnowledgeTag.base_id == base_id)
        )
        if row is None:
            raise not_found()
        await session.delete(row)
        await session.commit()
    return {"success": True}


@router.get(
    "/knowledge/{base_id}/documents/{document_id}/tag-definitions",
    response_model=KnowledgeTagListResponse,
)
async def list_document_tag_definitions(
    base_id: str,
    document_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with services_of(request).db.session() as session:
        document = await session.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == document_id,
                KnowledgeDocument.base_id == base_id,
            )
        )
        if document is None:
            raise not_found()
        rows = (
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
    return {"success": True, "data": [_tag_public(row) for row in rows]}


@router.post(
    "/knowledge/{base_id}/documents/{document_id}/tag-definitions",
    response_model=DocumentTagSaveResponse,
)
async def save_document_tag_definitions(
    base_id: str,
    document_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    definitions: list[Any] = (
        body["definitions"] if isinstance(body.get("definitions"), list) else []
    )
    created: list[dict[str, Any]] = []
    updated: list[dict[str, Any]] = []
    async with services_of(request).db.session() as session:
        document = await session.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == document_id,
                KnowledgeDocument.base_id == base_id,
            )
        )
        if document is None:
            raise not_found()
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
                    KnowledgeTag.base_id == base_id,
                    KnowledgeTag.tag_slot == slot,
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
                created.append(_tag_public(row))
            else:
                row.name = name[:128]
                row.field_type = field_type
                updated.append(_tag_public(row))
        await session.commit()
    return {"success": True, "data": {"created": created, "updated": updated, "errors": []}}


@router.delete(
    "/knowledge/{base_id}/documents/{document_id}/tag-definitions", response_model=SuccessResponse
)
async def delete_document_tag_definitions(
    base_id: str,
    document_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with services_of(request).db.session() as session:
        document = await session.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == document_id,
                KnowledgeDocument.base_id == base_id,
            )
        )
        if document is None:
            raise not_found()
        await session.execute(
            delete(KnowledgeDocumentTag).where(KnowledgeDocumentTag.document_id == document_id)
        )
        await session.commit()
    return {"success": True}


@router.post(
    "/knowledge/{base_id}/documents/uploads",
    status_code=201,
    response_model=KnowledgeUploadCreateResponse,
)
async def create_knowledge_upload(
    base_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    await _workspace_for_id(request, str(body.get("workspaceId") or "lingxi"), context)
    name = _safe_name(str(body.get("name") or "文档.txt"))
    content_type = _mime_type(name, body.get("contentType"))
    size = body.get("size")
    if isinstance(size, bool) or not isinstance(size, int) or size < 1:
        raise HTTPException(status_code=422, detail="invalid_file_size")
    if size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="file_too_large")
    upload_id = f"knowledge_upload_{uuid.uuid4().hex}"
    token = secrets.token_urlsafe(32)
    temp = _storage_root(request, context.learner_id) / f".{upload_id}.part"
    expires = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    workspace = await _workspace_for_id(request, str(body.get("workspaceId") or "lingxi"), context)
    async with services_of(request).db.session() as session:
        session.add(
            WorkspaceUploadSession(
                id=upload_id,
                workspace_id=workspace.id,
                learner_id=context.learner_id,
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                name=name,
                mime_type=content_type,
                size=size,
                temp_key=str(temp.relative_to(_storage_root(request, context.learner_id))),
                status="uploading",
                expires_at=datetime.fromisoformat(expires),
            )
        )
        await session.commit()
    item = {
        "id": upload_id,
        "knowledgeBaseId": base_id,
        "token": token,
        "body": {
            **body,
            "name": name,
            "contentType": content_type,
            "size": size,
            "purpose": "knowledge_document",
        },
        "learner_id": context.learner_id,
        "temp": temp,
        "workspace_id": workspace.id,
        "parts": {},
        "expiresAt": expires,
    }
    _upload_sessions[upload_id] = item
    session_public = _knowledge_upload_session_public(item, status="uploading", document=None)
    transfer = {
        "method": "put",
        "url": _public_origin(request) + f"/api/v2/uploads/{upload_id}",
        "headers": {"upload-token": token},
        "expiresAt": expires,
    }
    return {"data": {"session": session_public, "uploadToken": token, "transfer": transfer}}


@router.post("/knowledge/{base_id}/documents/uploads/{upload_id}/parts")
async def create_knowledge_upload_part_urls(
    base_id: str,
    upload_id: str,
    body: dict[str, Any],
    request: Request,
    workspaceId: str,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    item = _upload_sessions.get(upload_id)
    if item is None or item.get("knowledgeBaseId") != base_id:
        raise not_found()
    await _base_for_id(request, base_id, context)
    try:
        return multipart_part_urls(
            upload_id,
            item,
            context.learner_id,
            request.headers.get("upload-token"),
            body,
            _public_origin(request),
        )
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error


@router.post(
    "/knowledge/{base_id}/documents/uploads/{upload_id}/complete",
    response_model=UploadStateResponse,
)
async def complete_knowledge_upload(
    base_id: str,
    upload_id: str,
    request: Request,
    workspaceId: str,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    item = _upload_sessions.get(upload_id)
    if (
        item is None
        or item.get("knowledgeBaseId") != base_id
        or item["learner_id"] != context.learner_id
        or request.headers.get("upload-token") != item["token"]
    ):
        raise not_found()
    await _base_for_id(request, base_id, context)
    if item.get("status") == "completed" and item.get("document") is not None:
        return {
            "data": _knowledge_upload_session_public(
                item, status="completed", document=item["document"]
            )
        }
    if item["temp"].is_file():
        raw = item["temp"].read_bytes()
    elif item.get("parts"):
        raw = b"".join(
            path.read_bytes() for _number, path in sorted(item["parts"].items()) if path.is_file()
        )
    else:
        raw = b""
    if len(raw) != int(item["body"]["size"]):
        raise HTTPException(status_code=422, detail="upload_size_mismatch")
    name, mime, content = _parse_knowledge_document(
        {
            "name": item["body"]["name"],
            "content": base64.b64encode(raw).decode("ascii"),
            "encoding": "base64",
            "contentType": item["body"]["contentType"],
        }
    )
    metadata = {
        key: item["body"].get(key)
        for key in ("tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7")
        if item["body"].get(key) is not None
    }
    async with services_of(request).db.session() as session:
        row = KnowledgeDocument(
            id=f"doc_{uuid.uuid4().hex}",
            base_id=base_id,
            name=name,
            mime_type=mime,
            content=content,
            metadata_payload=metadata,
        )
        session.add(row)
        for ordinal, start in enumerate(range(0, len(content), 1200)):
            session.add(
                KnowledgeChunk(
                    id=f"chunk_{uuid.uuid4().hex}",
                    document_id=row.id,
                    ordinal=ordinal,
                    text=content[start : start + 1200],
                    metadata_payload={"enabled": True},
                )
            )
        upload_row = await session.get(WorkspaceUploadSession, upload_id)
        if upload_row is not None:
            upload_row.status = "completed"
            upload_row.file_id = row.id
        await session.commit()
    document = _document_public(row)
    summary = {
        key: document[key]
        for key in (
            "id",
            "knowledgeBaseId",
            "filename",
            "fileSize",
            "mimeType",
            "processingStatus",
            "chunkCount",
            "tokenCount",
            "characterCount",
            "enabled",
            "createdAt",
        )
    }
    item["status"] = "completed"
    item["document"] = summary
    item["temp"].unlink(missing_ok=True)
    for part_path in item.get("parts", {}).values():
        part_path.unlink(missing_ok=True)
    return {"data": _knowledge_upload_session_public(item, status="completed", document=summary)}


@router.delete("/knowledge/{base_id}/documents/uploads/{upload_id}")
async def abort_knowledge_upload(
    base_id: str,
    upload_id: str,
    request: Request,
    workspaceId: str,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    item = _upload_sessions.get(upload_id)
    if (
        item is None
        or item.get("knowledgeBaseId") != base_id
        or item["learner_id"] != context.learner_id
        or request.headers.get("upload-token") != item["token"]
    ):
        raise not_found()
    await _base_for_id(request, base_id, context)
    _upload_sessions.pop(upload_id, None)
    item["temp"].unlink(missing_ok=True)
    for part_path in item.get("parts", {}).values():
        part_path.unlink(missing_ok=True)
    async with services_of(request).db.session() as session:
        row = await session.get(WorkspaceUploadSession, upload_id)
        if row is not None:
            row.status = "aborted"
            await session.commit()
    return {"data": _knowledge_upload_session_public(item, status="aborted", document=None)}


@router.post("/knowledge/{base_id}/documents", response_model=KnowledgeDocumentResponse)
async def create_document(
    base_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    name, mime, content = _parse_knowledge_document(body)
    row = KnowledgeDocument(
        id=f"doc_{uuid.uuid4().hex}",
        base_id=base_id,
        name=name,
        mime_type=mime,
        content=content,
        metadata_payload=dict(body.get("metadata") or {}),
    )
    async with services_of(request).db.session() as session:
        session.add(row)
        # Deterministic chunks keep search and retrieval useful without embeddings.
        for ordinal, start in enumerate(range(0, len(content), 1200)):
            session.add(
                KnowledgeChunk(
                    id=f"chunk_{uuid.uuid4().hex}",
                    document_id=row.id,
                    ordinal=ordinal,
                    text=content[start : start + 1200],
                    metadata_payload={},
                )
            )
        await session.commit()
    public = _document_public(row)
    return {"success": True, "data": public, "document": public}


@router.post(
    "/knowledge/{base_id}/documents/upsert", response_model=KnowledgeDocumentUpsertResponse
)
async def upsert_document(
    base_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    document_id = str(body.get("documentId") or "").strip()
    name, mime, content = _parse_knowledge_document(body)
    async with services_of(request).db.session() as session:
        row = (
            await session.scalar(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.id == document_id, KnowledgeDocument.base_id == base_id
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
                mime_type=mime,
                content=content,
                metadata_payload={},
            )
            session.add(row)
        else:
            row.name, row.mime_type, row.content, row.archived = name, mime, content, False
            await session.execute(
                delete(KnowledgeChunk).where(KnowledgeChunk.document_id == row.id)
            )
        for ordinal, start in enumerate(range(0, len(content), 1200)):
            session.add(
                KnowledgeChunk(
                    id=f"chunk_{uuid.uuid4().hex}",
                    document_id=row.id,
                    ordinal=ordinal,
                    text=content[start : start + 1200],
                    metadata_payload={"enabled": True},
                )
            )
        await session.commit()
    return {
        "success": True,
        "data": {
            "documentsCreated": [{"documentId": row.id, "filename": row.name, "status": "pending"}],
            "isUpdate": is_update,
            "previousDocumentId": row.id if is_update else None,
            "processingMethod": "background",
            "processingConfig": {"maxConcurrentDocuments": 1, "batchSize": 1},
        },
    }


@router.patch("/knowledge/{base_id}/documents", response_model=KnowledgeBulkDocumentsResponse)
async def bulk_update_documents(
    base_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    operation = str(body.get("operation") or "")
    ids = {str(item) for item in body.get("documentIds") or []}
    if operation not in {"enable", "disable", "delete"} or not ids:
        raise HTTPException(status_code=422, detail="invalid_document_operation")
    async with services_of(request).db.session() as session:
        rows = list(
            (
                await session.execute(
                    select(KnowledgeDocument).where(
                        KnowledgeDocument.base_id == base_id, KnowledgeDocument.id.in_(ids)
                    )
                )
            )
            .scalars()
            .all()
        )
        for row in rows:
            row.archived = operation != "enable"
        await session.commit()
    return {
        "success": True,
        "data": {
            "operation": operation,
            "successCount": len(rows),
            "failedCount": len(ids) - len(rows),
            "updatedDocuments": [{"id": row.id, "enabled": not row.archived} for row in rows],
        },
    }


@router.get(
    "/knowledge/{base_id}/documents/{document_id}", response_model=KnowledgeDocumentResponse
)
async def get_document(
    base_id: str,
    document_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with services_of(request).db.session() as session:
        row = await session.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == document_id, KnowledgeDocument.base_id == base_id
            )
        )
    if row is None:
        raise not_found()
    public = _document_public(row)
    return {"success": True, "data": public, "document": public}


@router.get(
    "/knowledge/{base_id}/documents/{document_id}/chunks", response_model=KnowledgeChunksResponse
)
async def list_chunks(
    base_id: str,
    document_id: str,
    request: Request,
    search: str | None = None,
    enabled: str | None = None,
    limit: int = 50,
    offset: int = 0,
    sortBy: str | None = None,
    sortOrder: str | None = None,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with services_of(request).db.session() as session:
        document = await session.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == document_id, KnowledgeDocument.base_id == base_id
            )
        )
        if document is None:
            raise not_found()
        rows = (
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
        document = await session.get(KnowledgeDocument, document_id)
    if search:
        needle = search.casefold()
        rows = [row for row in rows if needle in (row.text or "").casefold()]
    if enabled in {"true", "false"}:
        want_enabled = enabled == "true"
        rows = [
            row
            for row in rows
            if bool((row.metadata_payload or {}).get("enabled", True)) == want_enabled
        ]
    if sortBy in {"chunkIndex", "tokenCount", "enabled"}:

        def chunk_sort_key(row: KnowledgeChunk) -> Any:
            values = {
                "chunkIndex": row.ordinal,
                "tokenCount": len(row.text or "") // 4,
                "enabled": bool((row.metadata_payload or {}).get("enabled", True)),
            }
            return values[sortBy]

        rows = sorted(rows, key=chunk_sort_key, reverse=sortOrder == "desc")
    total = len(rows)
    page = rows[max(0, offset) : max(0, offset) + min(100, max(1, limit))]
    chunks: list[dict[str, Any]] = []
    running_offset = 0
    for row in page:
        chunks.append(
            _chunk_public(
                row,
                document_created_at=document.created_at if document else None,
                document_updated_at=document.updated_at if document else None,
                start_offset=running_offset,
            )
        )
        running_offset += len(row.text or "")
    pagination = {
        "total": total,
        "limit": limit,
        "offset": offset,
        "hasMore": offset + len(chunks) < total,
    }
    return {"success": True, "data": chunks, "chunks": chunks, "pagination": pagination}


@router.post(
    "/knowledge/{base_id}/documents/{document_id}/chunks", response_model=KnowledgeChunkResponse
)
async def create_chunk(
    base_id: str,
    document_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    content = str(body.get("content") or "")
    if not content:
        raise HTTPException(status_code=422, detail="chunk_content_required")
    async with services_of(request).db.session() as session:
        document = await session.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == document_id, KnowledgeDocument.base_id == base_id
            )
        )
        if document is None:
            raise not_found()
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
            metadata_payload={"enabled": bool(body.get("enabled", True))},
        )
        session.add(row)
        await session.commit()
    return {
        "success": True,
        "data": _chunk_public(
            row, document_created_at=document.created_at, document_updated_at=document.updated_at
        ),
    }


@router.get(
    "/knowledge/{base_id}/documents/{document_id}/chunks/{chunk_id}",
    response_model=KnowledgeChunkResponse,
)
async def get_chunk(
    base_id: str,
    document_id: str,
    chunk_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with services_of(request).db.session() as session:
        document = await session.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == document_id, KnowledgeDocument.base_id == base_id
            )
        )
        row = await session.scalar(
            select(KnowledgeChunk).where(
                KnowledgeChunk.id == chunk_id, KnowledgeChunk.document_id == document_id
            )
        )
    if document is None or row is None:
        raise not_found()
    return {
        "success": True,
        "data": _chunk_public(
            row, document_created_at=document.created_at, document_updated_at=document.updated_at
        ),
    }


@router.put(
    "/knowledge/{base_id}/documents/{document_id}/chunks/{chunk_id}",
    response_model=KnowledgeChunkResponse,
)
@router.patch(
    "/knowledge/{base_id}/documents/{document_id}/chunks/{chunk_id}",
    response_model=KnowledgeChunkResponse,
)
async def update_chunk(
    base_id: str,
    document_id: str,
    chunk_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with services_of(request).db.session() as session:
        document = await session.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == document_id, KnowledgeDocument.base_id == base_id
            )
        )
        row = await session.scalar(
            select(KnowledgeChunk).where(
                KnowledgeChunk.id == chunk_id, KnowledgeChunk.document_id == document_id
            )
        )
        if document is None or row is None:
            raise not_found()
        if body.get("content") is not None:
            row.text = str(body["content"])
        metadata = {**(row.metadata_payload or {})}
        if body.get("enabled") is not None:
            metadata["enabled"] = bool(body["enabled"])
        row.metadata_payload = metadata
        await session.commit()
    return {
        "success": True,
        "data": _chunk_public(
            row, document_created_at=document.created_at, document_updated_at=document.updated_at
        ),
    }


@router.delete(
    "/knowledge/{base_id}/documents/{document_id}/chunks/{chunk_id}",
    response_model=KnowledgeMessageResponse,
)
async def delete_chunk(
    base_id: str,
    document_id: str,
    chunk_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with services_of(request).db.session() as session:
        row = await session.scalar(
            select(KnowledgeChunk).where(
                KnowledgeChunk.id == chunk_id, KnowledgeChunk.document_id == document_id
            )
        )
        if row is None:
            raise not_found()
        await session.delete(row)
        await session.commit()
    return {"success": True, "data": {"message": "deleted"}}


@router.patch(
    "/knowledge/{base_id}/documents/{document_id}/chunks",
    response_model=KnowledgeBulkChunksResponse,
)
async def bulk_update_chunks(
    base_id: str,
    document_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    operation = str(body.get("operation") or "")
    chunk_ids = {str(item) for item in body.get("chunkIds") or []}
    if operation not in {"enable", "disable", "delete"} or not chunk_ids:
        raise HTTPException(status_code=422, detail="invalid_chunk_operation")
    async with services_of(request).db.session() as session:
        rows = list(
            (
                await session.execute(
                    select(KnowledgeChunk).where(
                        KnowledgeChunk.document_id == document_id, KnowledgeChunk.id.in_(chunk_ids)
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
    return {
        "success": True,
        "data": {
            "operation": operation,
            "successCount": len(rows),
            "errorCount": 0,
            "processed": len(rows),
            "errors": [],
        },
    }


@router.put(
    "/knowledge/{base_id}/documents/{document_id}", response_model=KnowledgeDocumentResponse
)
@router.patch(
    "/knowledge/{base_id}/documents/{document_id}", response_model=KnowledgeDocumentResponse
)
async def update_document(
    base_id: str,
    document_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with services_of(request).db.session() as session:
        row = await session.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == document_id, KnowledgeDocument.base_id == base_id
            )
        )
        if row is None:
            raise not_found()
        if (row.metadata_payload or {}).get("readOnly") and any(
            key in body for key in ("name", "filename", "content", "enabled")
        ):
            raise HTTPException(status_code=403, detail="read_only_document")
        if body.get("name") is not None or body.get("filename") is not None:
            row.name = _safe_name(str(body.get("name") or body.get("filename")))
        if isinstance(body.get("content"), str):
            row.content = body["content"]
            await session.execute(
                delete(KnowledgeChunk).where(KnowledgeChunk.document_id == row.id)
            )
            for ordinal, start in enumerate(range(0, len(row.content), 1200)):
                session.add(
                    KnowledgeChunk(
                        id=f"chunk_{uuid.uuid4().hex}",
                        document_id=row.id,
                        ordinal=ordinal,
                        text=row.content[start : start + 1200],
                        metadata_payload={},
                    )
                )
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
                        KnowledgeDocumentTag.document_id == row.id,
                        KnowledgeDocumentTag.tag_id == tag.id,
                    )
                )
                value = str(body.get(slot) or "")
                if value:
                    if link is None:
                        session.add(
                            KnowledgeDocumentTag(document_id=row.id, tag_id=tag.id, value=value)
                        )
                    else:
                        link.value = value
                elif link is not None:
                    await session.delete(link)
        await session.commit()
    public = _document_public(row)
    return {"success": True, "data": public, "document": public}


@router.delete(
    "/knowledge/{base_id}/documents/{document_id}", response_model=KnowledgeMessageResponse
)
async def archive_document(
    base_id: str,
    document_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with services_of(request).db.session() as session:
        row = await session.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == document_id, KnowledgeDocument.base_id == base_id
            )
        )
        if row is None:
            raise not_found()
        row.archived = True
        await session.commit()
    return {"success": True}


@router.post(
    "/knowledge/{base_id}/documents/{document_id}/restore", response_model=KnowledgeDocumentResponse
)
async def restore_document(
    base_id: str,
    document_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with services_of(request).db.session() as session:
        row = await session.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == document_id, KnowledgeDocument.base_id == base_id
            )
        )
        if row is None:
            raise not_found()
        row.archived = False
        await session.commit()
    public = _document_public(row)
    return {"success": True, "data": public, "document": public}


# Skills ---------------------------------------------------------------------
