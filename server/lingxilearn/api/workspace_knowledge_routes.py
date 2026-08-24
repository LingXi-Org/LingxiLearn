"""Workspace API routes split by resource family."""

import base64
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Never

from fastapi import APIRouter, Depends, HTTPException, Request

from ..application.uploads import multipart_part_urls, upload_sessions
from ..application.workspace_errors import WorkspaceDomainError
from ..application.workspace_files import WorkspaceFileStorage
from ..application.workspace_knowledge_service import WorkspaceKnowledgeService
from ..contracts.rest_models import (
    DocumentTagSaveResponse,
    KnowledgeBaseResponse,
    KnowledgeBasesResponse,
    KnowledgeBulkChunksResponse,
    KnowledgeBulkDocumentsResponse,
    KnowledgeChunkResponse,
    KnowledgeChunksResponse,
    KnowledgeDocumentResponse,
    KnowledgeDocumentsResponse,
    KnowledgeDocumentUpsertResponse,
    KnowledgeMessageResponse,
    KnowledgeNextSlotResponse,
    KnowledgeSearchResponse,
    KnowledgeTagListResponse,
    KnowledgeTagResponse,
    KnowledgeTagsResponse,
    KnowledgeTagUsageResponse,
    KnowledgeUploadCreateResponse,
    SuccessResponse,
    UploadStateResponse,
)
from ..learner import LearnerContext
from .dependencies import current_learner_context, not_found, services_of
from .mappers.knowledge import chunk_response as _chunk_public
from .mappers.knowledge import document_response as _document_public
from .mappers.knowledge import knowledge_base_response as _knowledge_base_public
from .mappers.knowledge import (
    knowledge_upload_session_response as _knowledge_upload_session_public,
)
from .mappers.knowledge import tag_response as _tag_public
from .workspace_route_shared import (
    MAX_FILE_SIZE,
    _mime_type,
    _parse_knowledge_document,
    _public_origin,
    _safe_name,
    _storage_root,
    _workspace_for_id,
)

router = APIRouter(prefix="/api")


def _knowledge_service(request: Request) -> WorkspaceKnowledgeService:
    return services_of(request).workspace_knowledge


def _raise_domain(error: WorkspaceDomainError) -> Never:
    raise HTTPException(status_code=error.status_code, detail=error.code) from error


@router.get("/knowledge", response_model=KnowledgeBasesResponse)
async def list_knowledge(
    request: Request,
    includeArchived: bool = False,
    scope: str = "active",
    workspaceId: str | None = None,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await services_of(request).artifacts.project_agent_artifacts(context.learner_id)
    rows = await _knowledge_service(request).repository.list_bases(
        context.learner_id, scope, includeArchived
    )
    result = [_knowledge_base_public(row, count) for row, count in rows]
    return {"success": True, "data": result, "knowledgeBases": result}


@router.post("/knowledge", response_model=KnowledgeBaseResponse)
async def create_knowledge(
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    row = await _knowledge_service(request).repository.create_base(
        context.learner_id,
        str(body.get("name") or "知识库"),
        str(body.get("description") or ""),
    )
    public = _knowledge_base_public(row)
    return {"success": True, "data": public, "knowledgeBase": public}


async def _base_for_id(request: Request, base_id: str, context: LearnerContext) -> Any:
    try:
        return await _knowledge_service(request).require_base(context.learner_id, base_id)
    except WorkspaceDomainError as error:
        _raise_domain(error)


@router.get("/knowledge/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    request: Request,
    q: str = "",
    limit: int = 20,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """Search before the ``/{base_id}`` route so ``search`` is not a base id."""

    needle = q.strip().casefold()
    docs = await _knowledge_service(request).repository.search_documents(context.learner_id)
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
    rows = await _knowledge_service(request).repository.list_tags(base_id)
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
    rows = await _knowledge_service(request).repository.tag_usage(base_id)
    usages = []
    for tag, linked_documents in rows:
        documents = [
            {"id": document.id, "name": document.name, "tagValue": value}
            for document, value in linked_documents
        ]
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
    current = await _knowledge_service(request).repository.update_base(row.id, body)
    if current is None:
        raise not_found()
    public = _knowledge_base_public(current)
    return {"success": True, "data": public, "knowledgeBase": public}


@router.delete("/knowledge/{base_id}", response_model=KnowledgeMessageResponse)
async def archive_knowledge(
    base_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    row = await _base_for_id(request, base_id, context)
    await _knowledge_service(request).repository.set_base_archived(row.id, True)
    return {"success": True, "data": {"message": "archived"}}


@router.post("/knowledge/{base_id}/restore", response_model=KnowledgeBaseResponse)
async def restore_knowledge(
    base_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    row = await _base_for_id(request, base_id, context)
    row = await _knowledge_service(request).repository.set_base_archived(row.id, False) or row
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
    rows = await _knowledge_service(request).repository.list_documents(
        base_id, includeArchived, enabledFilter
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

        def sort_key(row: Any) -> Any:
            values = {
                "filename": row.name,
                "fileSize": len(row.content.encode("utf-8")),
                "tokenCount": len(row.content) // 4,
                "chunkCount": max(1, (len(row.content) + 1199) // 1200) if row.content else 0,
                "uploadedAt": row.created_at or datetime.now(UTC),
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
    rows = await _knowledge_service(request).repository.list_tags(base_id)
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
    row = await _knowledge_service(request).repository.create_tag(
        base_id, name, str(body.get("tagSlot") or ""), field_type
    )
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
    row = await _knowledge_service(request).repository.update_tag(base_id, tag_id, body)
    if row is None:
        raise not_found()
    return {"success": True, "data": _tag_public(row)}


@router.delete("/knowledge/{base_id}/tag-definitions/{tag_id}", response_model=SuccessResponse)
async def delete_tag_definition(
    base_id: str,
    tag_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    if not await _knowledge_service(request).repository.delete_tag(base_id, tag_id):
        raise not_found()
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
    if not await _knowledge_service(request).repository.document_exists(base_id, document_id):
        raise not_found()
    rows = await _knowledge_service(request).repository.list_tags(base_id)
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
    outcome = await _knowledge_service(request).repository.save_tag_definitions(
        base_id, document_id, definitions
    )
    if outcome is None:
        raise not_found()
    created_rows, updated_rows = outcome
    created = [_tag_public(row) for row in created_rows]
    updated = [_tag_public(row) for row in updated_rows]
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
    if not await _knowledge_service(request).repository.delete_document_tags(base_id, document_id):
        raise not_found()
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
    await services_of(request).workspace_files.create_upload(
        upload_id=upload_id,
        workspace_id=workspace.id,
        learner_id=context.learner_id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        name=name,
        mime_type=content_type,
        size=size,
        temp_key=str(temp.relative_to(_storage_root(request, context.learner_id))),
        expires_at=datetime.fromisoformat(expires),
    )
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
    upload_sessions[upload_id] = item
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
    item = upload_sessions.get(upload_id)
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
    item = upload_sessions.get(upload_id)
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
    raw = WorkspaceFileStorage.read_upload(item)
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
    row = await _knowledge_service(request).repository.create_document(
        base_id,
        name,
        mime,
        content,
        metadata,
        enabled_chunks=True,
        upload_id=upload_id,
    )
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
    WorkspaceFileStorage.cleanup_upload(item)
    return {"data": _knowledge_upload_session_public(item, status="completed", document=summary)}


@router.delete("/knowledge/{base_id}/documents/uploads/{upload_id}")
async def abort_knowledge_upload(
    base_id: str,
    upload_id: str,
    request: Request,
    workspaceId: str,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    item = upload_sessions.get(upload_id)
    if (
        item is None
        or item.get("knowledgeBaseId") != base_id
        or item["learner_id"] != context.learner_id
        or request.headers.get("upload-token") != item["token"]
    ):
        raise not_found()
    await _base_for_id(request, base_id, context)
    upload_sessions.pop(upload_id, None)
    WorkspaceFileStorage.cleanup_upload(item)
    await _knowledge_service(request).repository.set_upload_status(upload_id, "aborted")
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
    row = await _knowledge_service(request).repository.create_document(
        base_id, name, mime, content, dict(body.get("metadata") or {})
    )
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
    row, is_update = await _knowledge_service(request).repository.upsert_document(
        base_id, document_id, name, mime, content
    )
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
    rows = await _knowledge_service(request).repository.bulk_documents(base_id, ids, operation)
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
    row = await _knowledge_service(request).repository.find_document(base_id, document_id)
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
    outcome = await _knowledge_service(request).repository.document_chunks(base_id, document_id)
    if outcome is None:
        raise not_found()
    document, rows = outcome
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

        def chunk_sort_key(row: Any) -> Any:
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
    outcome = await _knowledge_service(request).repository.create_chunk(
        base_id, document_id, content, bool(body.get("enabled", True))
    )
    if outcome is None:
        raise not_found()
    document, row = outcome
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
    outcome = await _knowledge_service(request).repository.find_chunk(
        base_id, document_id, chunk_id
    )
    if outcome is None:
        raise not_found()
    document, row = outcome
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
    outcome = await _knowledge_service(request).repository.update_chunk(
        base_id, document_id, chunk_id, body
    )
    if outcome is None:
        raise not_found()
    document, row = outcome
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
    if not await _knowledge_service(request).repository.delete_chunk(
        base_id, document_id, chunk_id
    ):
        raise not_found()
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
    rows = await _knowledge_service(request).repository.bulk_chunks(
        base_id, document_id, chunk_ids, operation
    )
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
    try:
        row = await _knowledge_service(request).update_document(base_id, document_id, body)
    except WorkspaceDomainError as error:
        _raise_domain(error)
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
    row = await _knowledge_service(request).repository.set_document_archived(
        base_id, document_id, True
    )
    if row is None:
        raise not_found()
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
    row = await _knowledge_service(request).repository.set_document_archived(
        base_id, document_id, False
    )
    if row is None:
        raise not_found()
    public = _document_public(row)
    return {"success": True, "data": public, "document": public}


# Skills ---------------------------------------------------------------------
