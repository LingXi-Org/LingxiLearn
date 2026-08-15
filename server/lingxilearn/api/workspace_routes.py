"""Native Lingxi workspace API backed by the learner-owned Lingxi store.

Only the resource families implemented by Lingxi live here. In particular this module
does not expose workflow, enrichment, dispatch, deployment, or canvas routes.
The public ``lingxi`` workspace id is resolved to the authenticated learner's
private row on every request.
"""

from __future__ import annotations

import base64
import binascii
import csv
import hashlib
import io
import json
import math
import mimetypes
import re
import secrets
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from xml.etree import ElementTree

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import delete, desc, false, func, or_, select, update

from ..learner import LearnerContext
from ..store.models import (
    AgentTask,
    AgentTaskEvent,
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentTag,
    KnowledgeTag,
    PersonalSkill,
    Workspace,
    WorkspaceFile,
    WorkspaceFolder,
    WorkspacePinnedItem,
    WorkspaceTable,
    WorkspaceTableColumn,
    WorkspaceTableRow,
    WorkspaceTableView,
    WorkspaceUploadSession,
    utcnow,
)
from ..store.runtime_tables import (
    RUNTIME_COLUMN_LABELS,
    RUNTIME_COLUMNS_BY_CATEGORY,
    RUNTIME_STUDENT_CATEGORIES,
    RUNTIME_STUDENT_COLUMNS,
    ensure_runtime_tables,
)
from .routes import current_learner_context, not_found, service_of

router = APIRouter(prefix="/api")
MAX_FILE_SIZE = 20 * 1024 * 1024
ALLOWED_COLUMN_TYPES = {"string", "number", "currency", "boolean", "date", "json", "select"}
PINNED_RESOURCE_TYPES = {"workflow", "file", "knowledge_base", "table", "folder", "workspace"}


async def _workspace(request: Request, context: LearnerContext) -> Workspace:
    svc = service_of(request)
    async with svc.db.session() as session:
        row = await session.scalar(
            select(Workspace).where(Workspace.learner_id == context.learner_id)
        )
        if row is None:
            row = Workspace(
                id=f"ws_{secrets.token_urlsafe(18)}",
                learner_id=context.learner_id,
                name="灵犀智学",
                appearance={},
            )
            session.add(row)
            await session.commit()
        return row


async def _workspace_for_id(
    request: Request, workspace_id: str, context: LearnerContext
) -> Workspace:
    row = await _workspace(request, context)
    if workspace_id not in {"lingxi", row.id}:
        raise not_found()
    return row


def _public_workspace(row: Workspace) -> dict[str, Any]:
    return {
        "id": "lingxi",
        "workspaceId": "lingxi",
        "name": row.name,
        "ownerId": row.learner_id,
        "organizationId": None,
        "slug": "lingxi",
        "workspaceMode": "personal",
        "role": "admin",
        "membershipId": f"membership:{row.learner_id}",
        "permissions": "admin",
        "appearance": row.appearance or {},
        "ownerBilling": {"plan": "internal", "isPaid": False, "isPro": False},
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def _safe_name(value: str, fallback: str = "untitled") -> str:
    candidate = str(value).strip().replace("\x00", "")
    # Names are leaf values in the native workspace API. Reject separators and
    # traversal segments instead of silently normalizing them, so callers can
    # never mistake a rejected path for a successfully stored path.
    if not candidate or candidate in {".", ".."} or "/" in candidate or "\\" in candidate:
        if not candidate and fallback:
            return fallback
        raise HTTPException(status_code=422, detail="invalid_file_name")
    return candidate[:255] or fallback


def _storage_root(request: Request, learner_id: str) -> Path:
    root = service_of(request).settings.var_dir / "workspaces" / learner_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def _storage_target(request: Request, learner_id: str, storage_key: str) -> Path:
    """Resolve a storage key without allowing traversal or symlink escapes."""

    prefix = f"{learner_id}/"
    parts = Path(storage_key.replace("\\", "/")).parts
    if not storage_key.startswith(prefix) or ".." in parts or len(parts) != 2:
        raise not_found()
    root = _storage_root(request, learner_id).resolve()
    target = (root / parts[1]).resolve()
    if target.parent != root:
        raise not_found()
    return target


def _public_origin(request: Request) -> str:
    """Return the browser-visible origin when FastAPI is behind Next's proxy."""

    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    proto = request.headers.get("x-forwarded-proto", "http").split(",", 1)[0].strip()
    if host:
        return f"{proto}://{host}".rstrip("/")
    return str(request.base_url).rstrip("/")


def _mime_type(name: str, supplied: Any) -> str:
    value = str(supplied or mimetypes.guess_type(name)[0] or "application/octet-stream").strip()
    if not value or len(value) > 160 or any(ord(char) < 32 for char in value):
        raise HTTPException(status_code=422, detail="invalid_mime_type")
    return value


def _file_public(row: WorkspaceFile, workspace_id: str) -> dict[str, Any]:
    return {
        "id": row.id,
        "workspaceId": "lingxi",
        "name": row.name,
        "key": row.storage_key,
        "path": row.path or row.name,
        "url": f"/api/files/serve/{row.storage_key}",
        "size": row.size,
        "type": row.mime_type,
        "mimeType": row.mime_type,
        "width": row.width,
        "height": row.height,
        "uploadedBy": row.metadata_payload.get("uploadedBy", "learner")
        if row.metadata_payload
        else "learner",
        "folderId": row.folder_id,
        # v2 upload/file contracts require a canonical folder path and a
        # public uploader address. LingxiIdentity remains the source of the
        # real profile; this local address is deliberately non-identifying.
        "folderPath": "/",
        "uploadedByEmail": "learner@lingxilearn.local",
        "deletedAt": row.updated_at.isoformat() if row.archived and row.updated_at else None,
        "uploadedAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
        "storageContext": "workspace",
        "context": "workspace",
        "readOnly": bool((row.metadata_payload or {}).get("readOnly")),
        "metadata": row.metadata_payload or {},
    }


def _column_public(row: WorkspaceTableColumn) -> dict[str, Any]:
    opts = row.options or {}
    return {
        "id": row.id,
        "name": row.name,
        "key": row.key,
        "type": row.type,
        "position": row.position,
        "required": bool(opts.get("required", False)),
        "unique": bool(opts.get("unique", False)),
        "options": opts.get("options", []),
        "multiple": bool(opts.get("multiple", False)),
        "currencyCode": opts.get("currencyCode"),
    }


def _table_public(
    row: WorkspaceTable, columns: list[WorkspaceTableColumn], count: int = 0
) -> dict[str, Any]:
    public_columns = [
        _column_public(column) for column in sorted(columns, key=lambda item: item.position)
    ]
    metadata: dict[str, Any] = dict(row.metadata_payload or {})
    if metadata.get("source") == "lingxi-runtime":
        allowed_columns = RUNTIME_COLUMNS_BY_CATEGORY.get(
            str(metadata.get("category")), RUNTIME_STUDENT_COLUMNS
        )
        public_columns = [
            {**column, "name": RUNTIME_COLUMN_LABELS.get(column["key"], column["name"])}
            for column in public_columns
            if column["key"] in allowed_columns
        ]
    stored_locks: dict[str, Any] = (
        metadata["locks"] if isinstance(metadata.get("locks"), dict) else {}
    )
    locks = {
        "schemaLocked": bool(stored_locks.get("schemaLocked", False)),
        "insertLocked": bool(stored_locks.get("insertLocked", False)),
        "updateLocked": bool(stored_locks.get("updateLocked", False)),
        "deleteLocked": bool(stored_locks.get("deleteLocked", False)),
    }
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "workspaceId": "lingxi",
        "folderId": metadata.get("folderId"),
        "schema": {"columns": public_columns},
        "columns": public_columns,
        "metadata": metadata,
        "rowCount": count,
        "totalRows": count,
        "maxRows": 100_000,
        "createdBy": str(metadata.get("createdBy") or "lingxi-user"),
        "locks": locks,
        "archivedAt": row.updated_at.isoformat() if row.archived and row.updated_at else None,
        "archived": row.archived,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def _table_row_public(row: WorkspaceTableRow) -> dict[str, Any]:
    """Return the row shape consumed by the reused Sim table grid.

    Lingxi rows do not execute workflow groups, but the shared grid expects the
    execution map to be present so it can safely render ordinary data rows.
    """

    values = row.values or {}
    return {
        "id": row.id,
        "data": values,
        "values": values,
        "executions": {},
        "position": row.position,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def _view_public(row: WorkspaceTableView) -> dict[str, Any]:
    """Return the single table-view wire shape consumed by the web client."""

    return {
        "id": row.id,
        "tableId": row.table_id,
        "name": row.name,
        "config": row.config or {},
        "isDefault": bool(row.is_default),
        "createdBy": row.created_by,
        "createdAt": row.created_at.isoformat() if row.created_at else utcnow().isoformat(),
        "updatedAt": row.updated_at.isoformat() if row.updated_at else utcnow().isoformat(),
    }


async def _table_for_id(
    request: Request, table_id: str, context: LearnerContext
) -> tuple[Workspace, WorkspaceTable]:
    workspace = await _workspace(request, context)
    async with service_of(request).db.session() as session:
        table = await session.scalar(
            select(WorkspaceTable).where(
                WorkspaceTable.id == table_id, WorkspaceTable.workspace_id == workspace.id
            )
        )
        if table is None:
            raise not_found()
        return workspace, table


def _assert_table_writable(table: WorkspaceTable) -> None:
    if (table.metadata_payload or {}).get("source") == "lingxi-runtime":
        raise HTTPException(status_code=403, detail="learning_records_are_read_only")


def _knowledge_base_public(row: KnowledgeBase, document_count: int = 0) -> dict[str, Any]:
    return {
        "id": row.id,
        "userId": row.learner_id,
        "name": row.name,
        "description": row.description,
        "workspaceId": "lingxi",
        "documentCount": document_count,
        "docCount": document_count,
        "fileCount": document_count,
        "tokenCount": 0,
        "embeddingModel": "none",
        "embeddingDimension": 0,
        "chunkingConfig": {"maxSize": 1200, "minSize": 1, "overlap": 0, "strategy": "text"},
        "folderId": None,
        "deletedAt": row.updated_at.isoformat() if row.archived and row.updated_at else None,
        "archived": row.archived,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def _document_tag_values(row: KnowledgeDocument) -> dict[str, Any]:
    metadata: dict[str, Any] = dict(row.metadata_payload or {})
    return {
        key: metadata.get(key)
        for key in (
            "tag1",
            "tag2",
            "tag3",
            "tag4",
            "tag5",
            "tag6",
            "tag7",
            "number1",
            "number2",
            "number3",
            "number4",
            "number5",
            "date1",
            "date2",
            "boolean1",
            "boolean2",
            "boolean3",
        )
    }


def _document_public(row: KnowledgeDocument) -> dict[str, Any]:
    chunk_count = max(1, (len(row.content) + 1199) // 1200) if row.content else 0
    metadata: dict[str, Any] = dict(row.metadata_payload or {})
    return {
        "id": row.id,
        "knowledgeBaseId": row.base_id,
        "name": row.name,
        "filename": row.name,
        "fileUrl": f"data:{row.mime_type};base64,",
        "fileSize": len(row.content.encode("utf-8")),
        "mimeType": row.mime_type,
        "chunkCount": chunk_count,
        "tokenCount": max(0, len(row.content) // 4),
        "characterCount": len(row.content),
        "processingStatus": "completed",
        "processingError": None,
        "enabled": not row.archived,
        "uploadedAt": row.created_at.isoformat() if row.created_at else utcnow().isoformat(),
        "content": row.content,
        "size": len(row.content.encode("utf-8")),
        "status": "archived" if row.archived else "ready",
        "archived": row.archived,
        "metadata": metadata,
        "readOnly": bool(metadata.get("readOnly")),
        **_document_tag_values(row),
        "connectorId": metadata.get("connectorId"),
        "connectorType": metadata.get("connectorType"),
        "sourceUrl": metadata.get("sourceUrl"),
        "createdAt": row.created_at.isoformat() if row.created_at else utcnow().isoformat(),
        "updatedAt": row.updated_at.isoformat() if row.updated_at else utcnow().isoformat(),
    }


def _chunk_public(
    row: KnowledgeChunk,
    *,
    document_created_at: datetime | None = None,
    document_updated_at: datetime | None = None,
    start_offset: int = 0,
) -> dict[str, Any]:
    metadata: dict[str, Any] = dict(row.metadata_payload or {})
    content = row.text or ""
    return {
        "id": row.id,
        "chunkIndex": row.ordinal,
        "content": content,
        "contentLength": len(content),
        "tokenCount": max(0, len(content) // 4),
        "enabled": bool(metadata.get("enabled", True)),
        "startOffset": start_offset,
        "endOffset": start_offset + len(content),
        **{
            key: metadata.get(key)
            for key in (
                "tag1",
                "tag2",
                "tag3",
                "tag4",
                "tag5",
                "tag6",
                "tag7",
                "number1",
                "number2",
                "number3",
                "number4",
                "number5",
                "date1",
                "date2",
                "boolean1",
                "boolean2",
                "boolean3",
            )
        },
        "createdAt": (document_created_at or utcnow()).isoformat(),
        "updatedAt": (document_updated_at or document_created_at or utcnow()).isoformat(),
    }


def _tag_public(row: KnowledgeTag, fallback_slot: str = "") -> dict[str, Any]:
    slot = row.tag_slot or fallback_slot or row.id
    now = utcnow().isoformat()
    return {
        "id": row.id,
        "tagSlot": slot,
        "displayName": row.name,
        "name": row.name,
        "fieldType": row.field_type,
        "createdAt": now,
        "updatedAt": now,
    }


def _knowledge_upload_session_public(
    item: dict[str, Any],
    *,
    status: str,
    document: dict[str, Any] | None,
) -> dict[str, Any]:
    body = item["body"]
    return {
        "id": item["id"],
        "knowledgeBaseId": item["knowledgeBaseId"],
        "status": status,
        "name": body["name"],
        "contentType": body["contentType"],
        "size": int(body["size"]),
        "expiresAt": item["expiresAt"],
        "error": None,
        "document": document,
    }


def _parse_knowledge_document(body: dict[str, Any]) -> tuple[str, str, str]:
    """Return ``(name, mime, searchable_text)`` for native document uploads.

    The UI can send plain text directly or base64 bytes from a file picker. We
    keep parsing dependency-free for the common formats and use optional
    ``pypdf``/``python-docx``-style parsers when present in a deployment.
    """

    name = _safe_name(
        str(body.get("name") or body.get("fileName") or body.get("filename") or "文档.txt")
    )
    mime = _mime_type(name, body.get("mimeType") or body.get("contentType"))
    supplied = body.get("content", "")
    file_url = body.get("fileUrl")
    if not supplied and isinstance(file_url, str) and file_url.lower().startswith("data:"):
        header, _, encoded = file_url.partition(",")
        if ";base64" in header.lower():
            supplied = encoded
            body = {**body, "encoding": "base64"}
        else:
            supplied = unquote(encoded)
    if body.get("encoding") == "base64":
        try:
            raw = base64.b64decode(str(supplied), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise HTTPException(status_code=422, detail="invalid_base64_content") from exc
    elif isinstance(supplied, str):
        raw = supplied.encode("utf-8")
    else:
        raw = json.dumps(supplied, ensure_ascii=False).encode("utf-8")
    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="document_too_large")

    lower_mime = mime.casefold()
    suffix = Path(name).suffix.casefold()
    text: str
    if lower_mime in {"application/json", "text/json"} or suffix == ".json":
        try:
            text = json.dumps(json.loads(raw.decode("utf-8")), ensure_ascii=False, indent=2)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=422, detail="invalid_json_document") from exc
    elif lower_mime in {"text/csv", "application/csv"} or suffix == ".csv":
        try:
            rows = csv.reader(io.StringIO(raw.decode("utf-8-sig")))
            text = "\n".join("\t".join(cell.strip() for cell in row) for row in rows)
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=422, detail="invalid_csv_document") from exc
    elif lower_mime in {"text/html", "application/xhtml+xml"} or suffix in {".html", ".htm"}:
        text = unescape(re.sub(r"<[^>]+>", " ", raw.decode("utf-8", errors="replace")))
    elif (
        lower_mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        or suffix == ".docx"
    ):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                xml = archive.read("word/document.xml")
            root = ElementTree.fromstring(xml)
            text = " ".join(part for part in root.itertext() if part.strip())
        except (KeyError, ValueError, zipfile.BadZipFile) as exc:
            raise HTTPException(status_code=422, detail="invalid_docx_document") from exc
    elif lower_mime == "application/pdf" or suffix == ".pdf":
        text = ""
        try:
            from pypdf import PdfReader  # type: ignore[import-not-found]

            text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages)
        except Exception:  # noqa: BLE001 - optional parser; retain a safe fallback
            text = " ".join(
                unescape(match.decode("utf-8", errors="ignore"))
                for match in re.findall(rb"\(([^()]*)\)", raw)
            )
    else:
        text = raw.decode("utf-8", errors="replace")
    return name, mime, text[:MAX_FILE_SIZE]


# Workspaces -----------------------------------------------------------------


@router.get("/workspaces")
async def list_workspaces(
    request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    row = await _workspace(request, context)
    return {
        "workspaces": [_public_workspace(row)],
        "lastActiveWorkspaceId": "lingxi",
        "pinnedWorkspaceIds": [],
        "creationPolicy": None,
    }


@router.get("/workspaces/{workspace_id}")
async def get_workspace(
    workspace_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    row = await _workspace_for_id(request, workspace_id, context)
    return {"workspace": _public_workspace(row), "data": _public_workspace(row)}


@router.get("/workspaces/{workspace_id}/members")
async def list_workspace_members(
    workspace_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    await _workspace_for_id(request, workspace_id, context)
    return {
        "members": [
            {
                "userId": context.learner_id,
                "name": str(context.profile.get("displayName") or "学习者"),
                "image": None,
            }
        ]
    }


@router.get("/workspaces/{workspace_id}/permissions")
async def get_workspace_permissions(
    workspace_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    await _workspace_for_id(request, workspace_id, context)
    user = {
        "userId": context.learner_id,
        "email": f"{context.learner_id}@lingxilearn.local",
        "name": str(context.profile.get("displayName") or "学习者"),
        "image": None,
        "permissionType": "admin",
        "isExternal": False,
        "joinedAt": datetime.now(UTC).isoformat(),
        "roleSource": "owner",
        "isBilledAccount": True,
    }
    return {
        "users": [user],
        "total": 1,
        "viewer": {"userId": context.learner_id, "isAdmin": True, "permissionType": "admin"},
    }


@router.patch("/workspaces/{workspace_id}/permissions")
async def update_workspace_permissions(
    workspace_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, str]:
    """Acknowledge the shared write contract at the personal-workspace boundary.

    Lingxi workspaces have exactly one identity-owned member. There is no
    second organization permission store to mutate, but keeping this endpoint
    available prevents the reused settings shell from probing a removed route.
    The canonical membership representation remains the GET response above.
    """

    await _workspace_for_id(request, workspace_id, context)
    updates = body.get("updates")
    if not isinstance(updates, list) or not updates:
        raise HTTPException(status_code=422, detail="updates_required")
    return {"message": "Lingxi personal workspace permissions are identity-managed"}


@router.patch("/workspaces/{workspace_id}")
async def update_workspace(
    workspace_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    row = await _workspace_for_id(request, workspace_id, context)
    if "name" in body:
        row.name = str(body["name"]).strip()[:160] or row.name
    if "appearance" in body and isinstance(body["appearance"], dict):
        row.appearance = dict(body["appearance"])
    async with service_of(request).db.session() as session:
        current = await session.get(Workspace, row.id)
        if current is not None:
            current.name, current.appearance = row.name, row.appearance
        await session.commit()
    return {"workspace": _public_workspace(row), "data": _public_workspace(row)}


# Pins ----------------------------------------------------------------------


@router.get("/pinned-items")
async def list_pinned_items(
    request: Request,
    workspaceId: str,
    resourceType: str | None = None,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspaceId, context)
    if resourceType is not None and resourceType not in PINNED_RESOURCE_TYPES:
        raise HTTPException(status_code=422, detail="invalid_resource_type")
    async with service_of(request).db.session() as session:
        query = select(WorkspacePinnedItem).where(
            WorkspacePinnedItem.learner_id == context.learner_id,
            WorkspacePinnedItem.workspace_id == workspace.id,
        )
        if resourceType is not None:
            query = query.where(WorkspacePinnedItem.resource_type == resourceType)
        rows = (
            (await session.execute(query.order_by(WorkspacePinnedItem.pinned_at))).scalars().all()
        )
    return {"pinnedItems": [_pinned_item_public(row, context.learner_id) for row in rows]}


@router.post("/pinned-items")
async def create_pinned_item(
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, str(body.get("workspaceId") or "lingxi"), context)
    resource_type = str(body.get("resourceType") or "")
    resource_id = str(body.get("resourceId") or "").strip()
    if resource_type not in PINNED_RESOURCE_TYPES or not resource_id:
        raise HTTPException(status_code=422, detail="invalid_pinned_item")
    async with service_of(request).db.session() as session:
        row = await session.scalar(
            select(WorkspacePinnedItem).where(
                WorkspacePinnedItem.learner_id == context.learner_id,
                WorkspacePinnedItem.workspace_id == workspace.id,
                WorkspacePinnedItem.resource_type == resource_type,
                WorkspacePinnedItem.resource_id == resource_id,
            )
        )
        if row is None:
            row = WorkspacePinnedItem(
                id=f"pin_{uuid.uuid4().hex}",
                learner_id=context.learner_id,
                workspace_id=workspace.id,
                resource_type=resource_type,
                resource_id=resource_id,
            )
            session.add(row)
            await session.commit()
    return {"pinnedItem": _pinned_item_public(row, context.learner_id)}


@router.delete("/pinned-items/{resource_type}/{resource_id}")
async def delete_pinned_item(
    resource_type: str,
    resource_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    if resource_type not in PINNED_RESOURCE_TYPES:
        raise HTTPException(status_code=422, detail="invalid_resource_type")
    workspace = await _workspace(request, context)
    async with service_of(request).db.session() as session:
        row = await session.scalar(
            select(WorkspacePinnedItem).where(
                WorkspacePinnedItem.learner_id == context.learner_id,
                WorkspacePinnedItem.workspace_id == workspace.id,
                WorkspacePinnedItem.resource_type == resource_type,
                WorkspacePinnedItem.resource_id == resource_id,
            )
        )
        if row is not None:
            await session.delete(row)
            await session.commit()
    return {"success": True}


# Folders and files ----------------------------------------------------------


def _folder_public(row: WorkspaceFolder, workspace_id: str) -> dict[str, Any]:
    return {
        "id": row.id,
        "workspaceId": "lingxi",
        "userId": workspace_id,
        "name": row.name,
        "parentId": row.parent_id,
        "path": row.name,
        "sortOrder": 0,
        "deletedAt": row.updated_at.isoformat() if row.archived and row.updated_at else None,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("/workspaces/{workspace_id}/files/folders")
@router.get("/workspaces/{workspace_id}/folders")
async def list_folders(
    workspace_id: str,
    request: Request,
    scope: str = Query("active"),
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    async with service_of(request).db.session() as session:
        query = select(WorkspaceFolder).where(WorkspaceFolder.workspace_id == workspace.id)
        if scope in {"active", "archived"}:
            query = query.where(WorkspaceFolder.archived.is_(scope == "archived"))
        rows = (await session.execute(query.order_by(WorkspaceFolder.created_at))).scalars().all()
    folders = [_folder_public(row, workspace.id) for row in rows]
    return {"success": True, "folders": folders, "data": folders}


@router.post("/workspaces/{workspace_id}/files/folders", status_code=201)
@router.post("/workspaces/{workspace_id}/folders", status_code=201)
async def create_folder(
    workspace_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    folder = WorkspaceFolder(
        id=f"folder_{uuid.uuid4().hex}",
        workspace_id=workspace.id,
        parent_id=body.get("parentId"),
        name=_safe_name(str(body.get("name") or "新文件夹")),
    )
    async with service_of(request).db.session() as session:
        if folder.parent_id:
            parent = await session.scalar(
                select(WorkspaceFolder).where(
                    WorkspaceFolder.id == folder.parent_id,
                    WorkspaceFolder.workspace_id == workspace.id,
                )
            )
            if parent is None:
                raise not_found()
        session.add(folder)
        await session.commit()
    return {"success": True, "folder": _folder_public(folder, workspace.id)}


@router.patch("/workspaces/{workspace_id}/files/folders/{folder_id}")
@router.patch("/workspaces/{workspace_id}/folders/{folder_id}")
async def update_folder(
    workspace_id: str,
    folder_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    async with service_of(request).db.session() as session:
        folder = await session.scalar(
            select(WorkspaceFolder).where(
                WorkspaceFolder.id == folder_id, WorkspaceFolder.workspace_id == workspace.id
            )
        )
        if folder is None:
            raise not_found()
        if "name" in body:
            folder.name = _safe_name(str(body["name"]))
        # Folder ordering is intentionally a lightweight presentation value;
        # the native API keeps it in the response contract without another
        # mutable workflow-style ordering subsystem.
        if "parentId" in body:
            parent_id = body["parentId"] or None
            if parent_id:
                parent = await session.scalar(
                    select(WorkspaceFolder).where(
                        WorkspaceFolder.id == parent_id,
                        WorkspaceFolder.workspace_id == workspace.id,
                    )
                )
                if parent is None or parent.id == folder.id:
                    raise not_found()
            folder.parent_id = parent_id
        await session.commit()
        result = _folder_public(folder, workspace.id)
    return {"success": True, "folder": result}


@router.delete("/workspaces/{workspace_id}/files/folders/{folder_id}")
@router.delete("/workspaces/{workspace_id}/folders/{folder_id}")
async def archive_folder(
    workspace_id: str,
    folder_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    async with service_of(request).db.session() as session:
        folders = list(
            (
                await session.execute(
                    select(WorkspaceFolder).where(WorkspaceFolder.workspace_id == workspace.id)
                )
            )
            .scalars()
            .all()
        )
        folder = next((row for row in folders if row.id == folder_id), None)
        if folder is None:
            raise not_found()
        folder_ids = _descendant_folder_ids(folders, {folder_id})
        files = list(
            (
                await session.execute(
                    select(WorkspaceFile).where(WorkspaceFile.workspace_id == workspace.id)
                )
            )
            .scalars()
            .all()
        )
        for row in folders:
            if row.id in folder_ids:
                row.archived = True
        archived_files = 0
        for file_row in files:
            if file_row.folder_id in folder_ids:
                file_row.archived = True
                archived_files += 1
        await session.commit()
    return {"success": True, "deletedItems": {"folders": len(folder_ids), "files": archived_files}}


def _descendant_folder_ids(folders: list[WorkspaceFolder], roots: set[str]) -> set[str]:
    result = set(roots)
    changed = True
    while changed:
        changed = False
        for folder in folders:
            if folder.id not in result and folder.parent_id in result:
                result.add(folder.id)
                changed = True
    return result


@router.post("/workspaces/{workspace_id}/files/move")
async def move_file_items(
    workspace_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    file_ids = {str(item) for item in body.get("fileIds") or []}
    folder_ids = {str(item) for item in body.get("folderIds") or []}
    target_id = body.get("targetFolderId") or None
    async with service_of(request).db.session() as session:
        folders = list(
            (
                await session.execute(
                    select(WorkspaceFolder).where(WorkspaceFolder.workspace_id == workspace.id)
                )
            )
            .scalars()
            .all()
        )
        files = list(
            (
                await session.execute(
                    select(WorkspaceFile).where(WorkspaceFile.workspace_id == workspace.id)
                )
            )
            .scalars()
            .all()
        )
        folder_map = {row.id: row for row in folders}
        if target_id is not None and (
            target_id not in folder_map or folder_map[target_id].archived
        ):
            raise not_found()
        descendants = _descendant_folder_ids(folders, folder_ids)
        if target_id in descendants:
            raise HTTPException(status_code=422, detail="folder_cycle")
        if file_ids - {row.id for row in files} or folder_ids - set(folder_map):
            raise not_found()
        for file_row in files:
            if file_row.id in file_ids:
                file_row.folder_id = target_id
        for folder_row in folders:
            if folder_row.id in folder_ids:
                folder_row.parent_id = target_id
        await session.commit()
    return {"success": True, "movedItems": {"files": len(file_ids), "folders": len(folder_ids)}}


@router.post("/workspaces/{workspace_id}/files/bulk-archive")
async def bulk_archive_file_items(
    workspace_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    file_ids = {str(item) for item in body.get("fileIds") or []}
    root_folder_ids = {str(item) for item in body.get("folderIds") or []}
    async with service_of(request).db.session() as session:
        folders = list(
            (
                await session.execute(
                    select(WorkspaceFolder).where(WorkspaceFolder.workspace_id == workspace.id)
                )
            )
            .scalars()
            .all()
        )
        files = list(
            (
                await session.execute(
                    select(WorkspaceFile).where(WorkspaceFile.workspace_id == workspace.id)
                )
            )
            .scalars()
            .all()
        )
        folder_ids = _descendant_folder_ids(folders, root_folder_ids)
        if root_folder_ids - {row.id for row in folders} or file_ids - {row.id for row in files}:
            raise not_found()
        archived_files = 0
        for file_row in files:
            if file_row.id in file_ids or file_row.folder_id in folder_ids:
                if not file_row.archived:
                    archived_files += 1
                file_row.archived = True
        archived_folders = 0
        for folder_row in folders:
            if folder_row.id in folder_ids:
                if not folder_row.archived:
                    archived_folders += 1
                folder_row.archived = True
        await session.commit()
    return {"success": True, "deletedItems": {"folders": archived_folders, "files": archived_files}}


@router.post("/workspaces/{workspace_id}/files/folders/{folder_id}/restore")
@router.post("/workspaces/{workspace_id}/folders/{folder_id}/restore")
async def restore_folder(
    workspace_id: str,
    folder_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    async with service_of(request).db.session() as session:
        folders = list(
            (
                await session.execute(
                    select(WorkspaceFolder).where(WorkspaceFolder.workspace_id == workspace.id)
                )
            )
            .scalars()
            .all()
        )
        if folder_id not in {row.id for row in folders}:
            raise not_found()
        folder_ids = _descendant_folder_ids(folders, {folder_id})
        files = list(
            (
                await session.execute(
                    select(WorkspaceFile).where(WorkspaceFile.workspace_id == workspace.id)
                )
            )
            .scalars()
            .all()
        )
        for row in folders:
            if row.id in folder_ids:
                row.archived = False
        restored_files = 0
        for file_row in files:
            if file_row.folder_id in folder_ids and file_row.archived:
                file_row.archived = False
                restored_files += 1
        await session.commit()
    return {
        "success": True,
        "folder": _folder_public(next(row for row in folders if row.id == folder_id), workspace.id),
        "restoredItems": {"folders": len(folder_ids), "files": restored_files},
    }


@router.get("/workspaces/{workspace_id}/files/download")
async def download_file_items(
    workspace_id: str,
    request: Request,
    fileIds: list[str] | None = None,
    folderIds: list[str] | None = None,
    context: LearnerContext = Depends(current_learner_context),
) -> StreamingResponse:
    workspace = await _workspace_for_id(request, workspace_id, context)
    requested_files = {str(item) for item in (fileIds or [])}
    requested_folders = {str(item) for item in (folderIds or [])}
    async with service_of(request).db.session() as session:
        folders = list(
            (
                await session.execute(
                    select(WorkspaceFolder).where(WorkspaceFolder.workspace_id == workspace.id)
                )
            )
            .scalars()
            .all()
        )
        files = list(
            (
                await session.execute(
                    select(WorkspaceFile).where(
                        WorkspaceFile.workspace_id == workspace.id,
                        WorkspaceFile.archived.is_(False),
                    )
                )
            )
            .scalars()
            .all()
        )
    folder_ids = _descendant_folder_ids(folders, requested_folders)
    if requested_files - {row.id for row in files} or requested_folders - {
        row.id for row in folders
    }:
        raise not_found()
    selected = [row for row in files if row.id in requested_files or row.folder_id in folder_ids]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for row in selected:
            target = _storage_target(request, context.learner_id, row.storage_key)
            if target.is_file():
                archive.writestr(row.path or row.name, target.read_bytes())
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=lingxi-files.zip"},
    )


@router.get("/workspaces/{workspace_id}/files")
async def list_files(
    workspace_id: str,
    request: Request,
    scope: str = Query("active"),
    folderId: str | None = None,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    if scope not in {"active", "archived"}:
        raise HTTPException(status_code=400, detail="invalid_scope")
    await service_of(request).project_agent_artifacts(context.learner_id)
    workspace = await _workspace_for_id(request, workspace_id, context)
    async with service_of(request).db.session() as session:
        query = select(WorkspaceFile).where(WorkspaceFile.workspace_id == workspace.id)
        query = query.where(WorkspaceFile.archived == (scope == "archived"))
        if folderId is not None:
            query = query.where(WorkspaceFile.folder_id == folderId)
        rows = (
            (await session.execute(query.order_by(WorkspaceFile.updated_at.desc()))).scalars().all()
        )
    return {"success": True, "files": [_file_public(row, workspace.id) for row in rows]}


@router.post("/workspaces/{workspace_id}/files", status_code=201)
async def create_file(
    workspace_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    content = body.get("content", "")
    if body.get("encoding") == "base64":
        try:
            raw = base64.b64decode(str(content), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise HTTPException(status_code=422, detail="invalid_base64_content") from exc
    elif isinstance(content, str):
        raw = content.encode("utf-8")
    else:
        try:
            raw = base64.b64decode(str(content), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise HTTPException(status_code=422, detail="invalid_base64_content") from exc
    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="file_too_large")
    name = _safe_name(str(body.get("name") or body.get("fileName") or "untitled"))
    mime = _mime_type(name, body.get("type") or body.get("mimeType") or body.get("contentType"))
    folder_id = body.get("folderId") or None
    storage_key = f"{context.learner_id}/{secrets.token_urlsafe(24)}"
    if folder_id:
        async with service_of(request).db.session() as session:
            folder = await session.scalar(
                select(WorkspaceFolder).where(
                    WorkspaceFolder.id == folder_id,
                    WorkspaceFolder.workspace_id == workspace.id,
                    WorkspaceFolder.archived.is_(False),
                )
            )
            if folder is None:
                raise not_found()
    target = _storage_target(request, context.learner_id, storage_key)
    target.write_bytes(raw)
    row = WorkspaceFile(
        id=f"file_{uuid.uuid4().hex}",
        workspace_id=workspace.id,
        folder_id=folder_id,
        name=name,
        mime_type=mime,
        size=len(raw),
        storage_key=storage_key,
        path=name,
        metadata_payload={},
    )
    async with service_of(request).db.session() as session:
        session.add(row)
        await session.commit()
    return {"success": True, "file": _file_public(row, workspace.id)}


async def _file_for_id(
    request: Request, workspace_id: str, file_id: str, context: LearnerContext
) -> tuple[Workspace, WorkspaceFile]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    async with service_of(request).db.session() as session:
        row = await session.scalar(
            select(WorkspaceFile).where(
                WorkspaceFile.id == file_id, WorkspaceFile.workspace_id == workspace.id
            )
        )
        if row is None:
            raise not_found()
        return workspace, row


@router.get("/workspaces/{workspace_id}/files/{file_id}")
async def get_file(
    workspace_id: str,
    file_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace, row = await _file_for_id(request, workspace_id, file_id, context)
    return {
        "success": True,
        "file": _file_public(row, workspace.id),
        "data": _file_public(row, workspace.id),
    }


@router.patch("/workspaces/{workspace_id}/files/{file_id}")
async def update_file(
    workspace_id: str,
    file_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace, row = await _file_for_id(request, workspace_id, file_id, context)
    if (row.metadata_payload or {}).get("readOnly") and any(
        key in body for key in ("name", "folderId")
    ):
        raise HTTPException(status_code=403, detail="read_only_file")
    async with service_of(request).db.session() as session:
        current = await session.get(WorkspaceFile, row.id)
        if current is None:
            raise not_found()
        if "name" in body:
            current.name = _safe_name(str(body["name"]))
        if "folderId" in body:
            folder_id = body["folderId"] or None
            if folder_id:
                folder = await session.scalar(
                    select(WorkspaceFolder).where(
                        WorkspaceFolder.id == folder_id,
                        WorkspaceFolder.workspace_id == workspace.id,
                        WorkspaceFolder.archived.is_(False),
                    )
                )
                if folder is None:
                    raise not_found()
            current.folder_id = folder_id
        await session.commit()
        row = current
    return {"success": True, "file": _file_public(row, workspace.id)}


@router.patch("/workspaces/{workspace_id}/files/{file_id}/dimensions")
async def update_file_dimensions(
    workspace_id: str,
    file_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace, row = await _file_for_id(request, workspace_id, file_id, context)
    if body.get("key") != row.storage_key:
        return {"success": False}
    try:
        width, height = int(body.get("width", 0)), int(body.get("height", 0))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="invalid_dimensions") from exc
    if width <= 0 or height <= 0 or width > 100_000 or height > 100_000:
        raise HTTPException(status_code=422, detail="invalid_dimensions")
    async with service_of(request).db.session() as session:
        current = await session.get(WorkspaceFile, row.id)
        if current is not None:
            current.width, current.height = width, height
            await session.commit()
    return {"success": True}


@router.delete("/workspaces/{workspace_id}/files/{file_id}")
async def delete_file(
    workspace_id: str,
    file_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, row = await _file_for_id(request, workspace_id, file_id, context)
    async with service_of(request).db.session() as session:
        current = await session.get(WorkspaceFile, row.id)
        if current is not None:
            current.archived = True
            await session.commit()
    return {"success": True}


@router.post("/workspaces/{workspace_id}/files/{file_id}/restore")
async def restore_file(
    workspace_id: str,
    file_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, row = await _file_for_id(request, workspace_id, file_id, context)
    async with service_of(request).db.session() as session:
        current = await session.get(WorkspaceFile, row.id)
        if current is not None:
            current.archived = False
            await session.commit()
    return {"success": True}


@router.put("/workspaces/{workspace_id}/files/{file_id}/content")
async def update_file_content(
    workspace_id: str,
    file_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace, row = await _file_for_id(request, workspace_id, file_id, context)
    if (row.metadata_payload or {}).get("readOnly"):
        raise HTTPException(status_code=403, detail="read_only_file")
    content = body.get("content", "")
    if body.get("encoding") == "base64":
        try:
            raw = base64.b64decode(str(content), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise HTTPException(status_code=422, detail="invalid_base64_content") from exc
    else:
        if isinstance(content, str):
            raw = content.encode("utf-8")
        else:
            try:
                raw = base64.b64decode(str(content), validate=True)
            except (ValueError, binascii.Error) as exc:
                raise HTTPException(status_code=422, detail="invalid_base64_content") from exc
    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="file_too_large")
    old_target = _storage_target(request, context.learner_id, row.storage_key)
    storage_key = f"{context.learner_id}/{secrets.token_urlsafe(24)}"
    target = _storage_target(request, context.learner_id, storage_key)
    target.write_bytes(raw)
    async with service_of(request).db.session() as session:
        current = await session.get(WorkspaceFile, row.id)
        if current is None:
            raise not_found()
        current.size = len(raw)
        current.storage_key = storage_key
        await session.commit()
        row = current
    old_target.unlink(missing_ok=True)
    return {"success": True, "file": _file_public(row, workspace.id)}


@router.get("/workspaces/{workspace_id}/files/{file_id}/content")
async def get_file_content(
    workspace_id: str,
    file_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace, row = await _file_for_id(request, workspace_id, file_id, context)
    target = _storage_target(request, context.learner_id, row.storage_key)
    if not target.is_file():
        raise not_found()
    raw = target.read_bytes()
    try:
        content = raw.decode("utf-8")
        encoding = "utf-8"
    except UnicodeDecodeError:
        content = base64.b64encode(raw).decode("ascii")
        encoding = "base64"
    return {
        "success": True,
        "file": _file_public(row, workspace.id),
        "content": content,
        "encoding": encoding,
    }


@router.get("/files/serve/{storage_key:path}")
async def serve_file(
    storage_key: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> FileResponse:
    if ".." in Path(storage_key).parts or not storage_key.startswith(f"{context.learner_id}/"):
        raise not_found()
    async with service_of(request).db.session() as session:
        row = await session.scalar(
            select(WorkspaceFile).where(
                WorkspaceFile.storage_key == storage_key, WorkspaceFile.archived.is_(False)
            )
        )
    if row is None:
        raise not_found()
    target = _storage_target(request, context.learner_id, storage_key)
    if not target.is_file():
        raise not_found()
    return FileResponse(target, media_type=row.mime_type, filename=row.name)


@router.get("/workspaces/{workspace_id}/files/inline")
async def inline_file(
    workspace_id: str,
    request: Request,
    key: str | None = None,
    fileId: str | None = None,
    context: LearnerContext = Depends(current_learner_context),
) -> FileResponse:
    workspace = await _workspace_for_id(request, workspace_id, context)
    if bool(key) == bool(fileId):
        raise HTTPException(status_code=422, detail="provide_exactly_one_file_reference")
    async with service_of(request).db.session() as session:
        if fileId:
            row = await session.scalar(
                select(WorkspaceFile).where(
                    WorkspaceFile.id == fileId,
                    WorkspaceFile.workspace_id == workspace.id,
                    WorkspaceFile.archived.is_(False),
                )
            )
        else:
            row = await session.scalar(
                select(WorkspaceFile).where(
                    WorkspaceFile.storage_key == key,
                    WorkspaceFile.workspace_id == workspace.id,
                    WorkspaceFile.archived.is_(False),
                )
            )
    if row is None:
        raise not_found()
    target = _storage_target(request, context.learner_id, row.storage_key)
    if not target.is_file():
        raise not_found()
    return FileResponse(target, media_type=row.mime_type, filename=row.name)


@router.post("/workspaces/{workspace_id}/files/{file_id}/download")
async def file_download_url(
    workspace_id: str,
    file_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace, row = await _file_for_id(request, workspace_id, file_id, context)
    if row.archived:
        raise not_found()
    url = f"/api/files/serve/{row.storage_key}?context=workspace"
    return {
        "success": True,
        "downloadUrl": url,
        "viewerUrl": url,
        "fileName": row.name,
        "expiresIn": None,
    }


@router.get("/files/storage-status")
async def storage_status() -> dict[str, bool]:
    # LingxiLearn deliberately uses its local persistent volume; no cloud
    # provider is configured or exposed by this workspace surface.
    return {"cloudConfigured": False}


@router.get("/users/me/usage-limits")
async def usage_limits(
    request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    workspace = await _workspace(request, context)
    async with service_of(request).db.session() as session:
        used = (
            await session.scalar(
                select(func.coalesce(func.sum(WorkspaceFile.size), 0)).where(
                    WorkspaceFile.workspace_id == workspace.id, WorkspaceFile.archived.is_(False)
                )
            )
            or 0
        )
    limit = MAX_FILE_SIZE * 100
    empty_rate = {
        "isLimited": False,
        "requestsPerMinute": 0,
        "maxBurst": 0,
        "remaining": 0,
        "resetAt": (datetime.now(UTC) + timedelta(minutes=1)).isoformat(),
    }
    return {
        "success": True,
        "rateLimit": {"sync": empty_rate, "async": empty_rate, "authType": "manual"},
        "usage": {"currentPeriodCost": 0, "limit": 0, "plan": "internal"},
        "storage": {
            "usedBytes": int(used),
            "limitBytes": limit,
            "percentUsed": min(100, int(used) * 100 / limit),
        },
    }


# Upload session compatibility (local single-process transfer) ----------------

_upload_sessions: dict[str, dict[str, Any]] = {}


@router.post("/files/uploads")
async def create_upload(
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    purpose = str(body.get("purpose") or "workspace_file")
    if purpose not in {"workspace_file", "mothership_attachment"}:
        raise HTTPException(status_code=422, detail="unsupported_upload_purpose")
    if not isinstance(body.get("name"), str) or not body["name"].strip():
        raise HTTPException(status_code=422, detail="name_required")
    if not isinstance(body.get("contentType"), str) or not body["contentType"].strip():
        raise HTTPException(status_code=422, detail="content_type_required")
    supplied_size = body.get("size")
    if isinstance(supplied_size, bool) or not isinstance(supplied_size, int):
        raise HTTPException(status_code=422, detail="invalid_file_size")
    try:
        size = int(supplied_size)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="invalid_file_size") from exc
    if size < 0 or (purpose == "mothership_attachment" and size == 0):
        raise HTTPException(status_code=422, detail="invalid_file_size")
    if size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="file_too_large")
    upload_id = f"upload_{uuid.uuid4().hex}"
    token = secrets.token_urlsafe(32)
    temp = _storage_root(request, context.learner_id) / f".{upload_id}.part"
    workspace = await _workspace_for_id(request, str(body.get("workspaceId", "lingxi")), context)
    expires = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    async with service_of(request).db.session() as session:
        session.add(
            WorkspaceUploadSession(
                id=upload_id,
                workspace_id=workspace.id,
                learner_id=context.learner_id,
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                name=_safe_name(str(body.get("name") or "untitled")),
                mime_type=_mime_type(str(body.get("name") or "untitled"), body.get("contentType")),
                size=size,
                temp_key=str(temp.relative_to(_storage_root(request, context.learner_id))),
                status="uploading",
                expires_at=datetime.fromisoformat(expires),
            )
        )
        await session.commit()
    _upload_sessions[upload_id] = {
        "token": token,
        "body": body,
        "learner_id": context.learner_id,
        "temp": temp,
        "workspace_id": workspace.id,
        "parts": {},
        "expiresAt": expires,
    }
    upload_session = {
        "id": upload_id,
        "purpose": body.get("purpose", "workspace_file"),
        "status": "uploading",
        "name": body.get("name", "untitled"),
        "contentType": body.get("contentType", "application/octet-stream"),
        "size": size,
        "expiresAt": expires,
        "error": None,
        "result": None,
    }
    transfer = {
        "method": "put",
        "url": _public_origin(request) + f"/api/v2/uploads/{upload_id}",
        "headers": {"upload-token": token},
        "expiresAt": expires,
    }
    return {"data": {"session": upload_session, "uploadToken": token, "transfer": transfer}}


@router.put("/v2/uploads/{upload_id}")
async def put_upload(
    upload_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> StreamingResponse:
    item = _upload_sessions.get(upload_id)
    if (
        item is None
        or item["learner_id"] != context.learner_id
        or request.headers.get("upload-token") != item["token"]
    ):
        raise not_found()
    raw = await request.body()
    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="file_too_large")
    expected_size = int(item["body"].get("size", 0) or 0)
    if len(raw) != expected_size:
        raise HTTPException(status_code=422, detail="upload_size_mismatch")
    item["temp"].write_bytes(raw)
    async with service_of(request).db.session() as session:
        row = await session.get(WorkspaceUploadSession, upload_id)
        if row is not None:
            row.status = "uploaded"
            await session.commit()
    return StreamingResponse(iter(()), status_code=204)


@router.post("/files/uploads/{upload_id}/parts")
async def create_upload_part_urls(
    upload_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """Provide local multipart compatibility URLs for native upload hooks.

    Lingxi normally selects the single PUT transfer above. Keeping this small
    part-url surface makes the v0.8.0 contract deterministic for callers that
    explicitly request multipart transfer without introducing S3 state.
    """

    item = _upload_sessions.get(upload_id)
    if (
        item is None
        or item["learner_id"] != context.learner_id
        or request.headers.get("upload-token") != item["token"]
    ):
        raise not_found()
    numbers = body.get("partNumbers")
    if not isinstance(numbers, list) or not numbers or len(numbers) > 100:
        raise HTTPException(status_code=422, detail="invalid_part_numbers")
    try:
        part_numbers = sorted({int(number) for number in numbers})
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="invalid_part_numbers") from exc
    if any(number < 1 for number in part_numbers):
        raise HTTPException(status_code=422, detail="invalid_part_numbers")
    expires = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    parts = [
        {
            "partNumber": number,
            "url": _public_origin(request)
            + f"/api/v2/uploads/{upload_id}/parts/{number}?token={item['token']}",
            "headers": {},
            "expiresAt": expires,
        }
        for number in part_numbers
    ]
    return {"data": {"parts": parts}}


@router.put("/v2/uploads/{upload_id}/parts/{part_number}", status_code=204)
async def put_upload_part(
    upload_id: str,
    part_number: int,
    request: Request,
    token: str | None = None,
    context: LearnerContext = Depends(current_learner_context),
) -> Response:
    item = _upload_sessions.get(upload_id)
    if (
        item is None
        or item["learner_id"] != context.learner_id
        or token != item["token"]
        or part_number < 1
    ):
        raise not_found()
    raw = await request.body()
    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="file_too_large")
    part_path = item["temp"].with_name(f"{item['temp'].name}.{part_number}")
    part_path.write_bytes(raw)
    item["parts"][part_number] = part_path
    return Response(status_code=204)


@router.post("/files/uploads/{upload_id}/complete")
async def complete_upload(
    upload_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    item = _upload_sessions.get(upload_id)
    if (
        item is None
        or item["learner_id"] != context.learner_id
        or request.headers.get("upload-token") != item["token"]
    ):
        raise not_found()
    body = item["body"]
    if item.get("status") == "completed" and item.get("result") is not None:
        return {
            "data": {
                "id": upload_id,
                "purpose": body.get("purpose", "workspace_file"),
                "status": "completed",
                "name": body.get("name", "untitled"),
                "contentType": body.get("contentType", "application/octet-stream"),
                "size": int(body.get("size", 0) or 0),
                "expiresAt": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                "error": None,
                "result": item["result"],
            }
        }
    if item["temp"].is_file():
        raw = item["temp"].read_bytes()
    elif item.get("parts"):
        raw = b"".join(
            path.read_bytes() for _number, path in sorted(item["parts"].items()) if path.is_file()
        )
    else:
        raw = b""
    try:
        expected_size = int(body.get("size", 0) or 0)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="invalid_file_size") from exc
    if len(raw) != expected_size:
        raise HTTPException(status_code=422, detail="upload_size_mismatch")
    body = item["body"]
    workspace = await _workspace_for_id(request, str(body.get("workspaceId", "lingxi")), context)
    name = _safe_name(str(body.get("name") or "untitled"))
    folder_id = body.get("folderId") or None
    mime = _mime_type(name, body.get("contentType"))
    if folder_id:
        async with service_of(request).db.session() as session:
            folder = await session.scalar(
                select(WorkspaceFolder).where(
                    WorkspaceFolder.id == folder_id,
                    WorkspaceFolder.workspace_id == workspace.id,
                    WorkspaceFolder.archived.is_(False),
                )
            )
            if folder is None:
                raise not_found()
    storage_key = f"{context.learner_id}/{secrets.token_urlsafe(24)}"
    target = _storage_target(request, context.learner_id, storage_key)
    target.write_bytes(raw)
    row = WorkspaceFile(
        id=f"file_{uuid.uuid4().hex}",
        workspace_id=workspace.id,
        folder_id=folder_id,
        name=name,
        mime_type=mime,
        size=len(raw),
        storage_key=storage_key,
        path=name,
        metadata_payload={"purpose": body.get("purpose", "workspace_file")},
    )
    async with service_of(request).db.session() as session:
        session.add(row)
        upload_row = await session.get(WorkspaceUploadSession, upload_id)
        if upload_row is not None:
            upload_row.status = "completed"
            upload_row.file_id = row.id
        await session.commit()
    item["temp"].unlink(missing_ok=True)
    for part_path in item.get("parts", {}).values():
        part_path.unlink(missing_ok=True)
    public_file = _file_public(row, workspace.id)
    item["result"] = (
        {
            "path": public_file["path"],
            "key": public_file["key"],
            "name": public_file["name"],
            "size": public_file["size"],
            "type": public_file["type"],
        }
        if body.get("purpose") == "mothership_attachment"
        else public_file
    )
    item["status"] = "completed"
    return {
        "data": {
            "id": upload_id,
            "purpose": body.get("purpose", "workspace_file"),
            "status": "completed",
            "name": name,
            "contentType": row.mime_type,
            "size": row.size,
            "expiresAt": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "error": None,
            "result": item["result"],
        }
    }


@router.delete("/files/uploads/{upload_id}")
async def abort_upload(
    upload_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    item = _upload_sessions.get(upload_id)
    if (
        item is None
        or item["learner_id"] != context.learner_id
        or request.headers.get("upload-token") != item["token"]
    ):
        raise not_found()
    _upload_sessions.pop(upload_id, None)
    item["temp"].unlink(missing_ok=True)
    for part_path in item.get("parts", {}).values():
        part_path.unlink(missing_ok=True)
    async with service_of(request).db.session() as session:
        row = await session.get(WorkspaceUploadSession, upload_id)
        if row is not None:
            row.status = "aborted"
            await session.commit()
    body = item["body"]
    return {
        "data": {
            "id": upload_id,
            "purpose": body.get("purpose", "workspace_file"),
            "status": "aborted",
            "name": body.get("name", "untitled"),
            "contentType": body.get("contentType", "application/octet-stream"),
            "size": int(body.get("size", 0) or 0),
            "expiresAt": item.get("expiresAt")
            or (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "error": None,
            "result": None,
        }
    }


# Tables ---------------------------------------------------------------------


def _csv_payload(raw: str, delimiter: str = ",") -> tuple[list[str], list[dict[str, Any]]]:
    reader = csv.DictReader(io.StringIO(raw), delimiter=delimiter)
    headers = [str(item or "column").strip() or "column" for item in (reader.fieldnames or [])]
    return headers, [
        {key: value for key, value in row.items() if key is not None} for row in reader
    ]


@router.post("/table/import-csv", status_code=201)
async def import_table_csv(
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, str(body.get("workspaceId", "lingxi")), context)
    raw = str(body.get("csv") or body.get("content") or "")
    if len(raw.encode("utf-8")) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="import_too_large")
    headers, rows = _csv_payload(raw, str(body.get("delimiter") or ","))
    if not headers:
        raise HTTPException(status_code=422, detail="csv_header_required")
    table = WorkspaceTable(
        id=f"table_{uuid.uuid4().hex}",
        workspace_id=workspace.id,
        name=str(body.get("name") or "CSV 表格"),
        description="",
        metadata_payload={},
    )
    async with service_of(request).db.session() as session:
        session.add(table)
        for position, name in enumerate(headers):
            session.add(
                WorkspaceTableColumn(
                    id=f"col_{uuid.uuid4().hex}",
                    table_id=table.id,
                    key=name,
                    name=name,
                    type="string",
                    position=position,
                    options={},
                )
            )
        for position, values in enumerate(rows):
            session.add(
                WorkspaceTableRow(
                    id=f"row_{uuid.uuid4().hex}",
                    table_id=table.id,
                    values=values,
                    position=position,
                )
            )
        await session.commit()
    return {
        "success": True,
        "data": {"table": {"id": table.id, "name": table.name}, "importedRows": len(rows)},
    }


@router.post("/table/{table_id}/import")
async def import_table_rows(
    table_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    raw = str(body.get("csv") or body.get("content") or "")
    _headers, rows = (
        _csv_payload(raw, str(body.get("delimiter") or ","))
        if raw
        else ([], body.get("rows") or [])
    )
    if body.get("mode") == "replace":
        async with service_of(request).db.session() as session:
            await session.execute(
                delete(WorkspaceTableRow).where(WorkspaceTableRow.table_id == table.id)
            )
            for position, values in enumerate(rows):
                if isinstance(values, dict):
                    normalized = await _coerce_row_values(
                        session, table.id, dict(values), enforce_required=True
                    )
                    session.add(
                        WorkspaceTableRow(
                            id=f"row_{uuid.uuid4().hex}",
                            table_id=table.id,
                            values=normalized,
                            position=position,
                        )
                    )
            await session.commit()
    else:
        await create_rows(table_id, {"rows": rows}, request, context)
    return {"success": True, "data": {"importedRows": len(rows)}}


@router.get("/table")
async def list_tables(
    request: Request,
    workspaceId: str = "lingxi",
    scope: str = "active",
    includeArchived: bool | None = None,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspaceId, context)
    async with service_of(request).db.session() as session:
        if workspaceId == "lingxi":
            await ensure_runtime_tables(session, workspace.id)
            await session.commit()
        query = select(WorkspaceTable).where(WorkspaceTable.workspace_id == workspace.id)
        if scope not in {"active", "archived", "all"}:
            raise HTTPException(status_code=400, detail="invalid_scope")
        if scope in {"active", "archived"}:
            query = query.where(WorkspaceTable.archived.is_(scope == "archived"))
        elif includeArchived is False:
            query = query.where(WorkspaceTable.archived.is_(False))
        tables = (
            (await session.execute(query.order_by(WorkspaceTable.updated_at.desc())))
            .scalars()
            .all()
        )
        result = []
        for table in tables:
            metadata = table.metadata_payload or {}
            if (
                metadata.get("source") == "lingxi-runtime"
                and metadata.get("category") not in RUNTIME_STUDENT_CATEGORIES
            ):
                continue
            cols = (
                (
                    await session.execute(
                        select(WorkspaceTableColumn).where(
                            WorkspaceTableColumn.table_id == table.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            count = (
                await session.scalar(
                    select(func.count())
                    .select_from(WorkspaceTableRow)
                    .where(WorkspaceTableRow.table_id == table.id)
                )
                or 0
            )
            result.append(_table_public(table, list(cols), int(count)))
    return {
        "success": True,
        "data": {"tables": result, "totalCount": len(result)},
        "tables": result,
        "totalCount": len(result),
    }


@router.post("/lingxi/learning-records")
async def record_learning_event(
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """Project a replayed runtime event into the canonical runtime tables."""
    task_id = str(body.get("taskId") or "").strip()
    event = body.get("event") or {}
    sequence = int(event.get("sequence") or 0)
    if not task_id or sequence <= 0:
        raise HTTPException(status_code=422, detail="taskId_and_event_sequence_required")
    kind = str(event.get("kind") or "")
    projection = await service_of(request).repo.project_runtime_event(
        learner_id=context.learner_id,
        record_key=f"task:{task_id}:{sequence}",
        task_id=task_id,
        sequence=sequence,
        kind=kind,
        agent=str(event.get("agent") or ""),
        payload=event.get("payload") or {},
        runtime=event.get("runtime") or {},
        execution_id=event.get("execution_id"),
    )
    return {
        "success": True,
        "data": {
            "taskId": task_id,
            "sequence": sequence,
            "table": projection["table"],
            "category": projection["category"],
            "action": projection["action"],
        },
    }


def _pinned_item_public(row: WorkspacePinnedItem, learner_id: str) -> dict[str, Any]:
    return {
        "id": row.id,
        "userId": learner_id,
        "workspaceId": "lingxi",
        "resourceType": row.resource_type,
        "resourceId": row.resource_id,
        "pinnedAt": row.pinned_at.isoformat() if row.pinned_at else None,
    }


@router.post("/table")
async def create_table(
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, str(body.get("workspaceId", "lingxi")), context)
    schema = body.get("schema") or {}
    columns = schema.get("columns") or []
    if not columns:
        raise HTTPException(status_code=422, detail="at_least_one_column_required")
    table = WorkspaceTable(
        id=f"table_{uuid.uuid4().hex}",
        workspace_id=workspace.id,
        name=str(body.get("name") or "新表格"),
        description=str(body.get("description") or ""),
        metadata_payload={"folderId": body.get("folderId") or None},
    )
    async with service_of(request).db.session() as session:
        session.add(table)
        for index, column in enumerate(columns):
            ctype = str(column.get("type", "string"))
            if ctype not in ALLOWED_COLUMN_TYPES:
                raise HTTPException(status_code=422, detail="unsupported_column_type")
            name = str(column.get("name") or f"column_{index + 1}")
            session.add(
                WorkspaceTableColumn(
                    id=str(column.get("id") or f"col_{uuid.uuid4().hex}"),
                    table_id=table.id,
                    key=name,
                    name=name,
                    type=ctype,
                    position=int(column.get("position", index)),
                    options={
                        k: column[k]
                        for k in ("required", "unique", "options", "multiple", "currencyCode")
                        if k in column
                    },
                )
            )
        for index in range(int(body.get("initialRowCount", 0) or 0)):
            session.add(
                WorkspaceTableRow(
                    id=f"row_{uuid.uuid4().hex}", table_id=table.id, values={}, position=index
                )
            )
        await session.commit()
    async with service_of(request).db.session() as session:
        persisted_columns = (
            (
                await session.execute(
                    select(WorkspaceTableColumn).where(WorkspaceTableColumn.table_id == table.id)
                )
            )
            .scalars()
            .all()
        )
        row_count = (
            await session.scalar(
                select(func.count())
                .select_from(WorkspaceTableRow)
                .where(WorkspaceTableRow.table_id == table.id)
            )
            or 0
        )
    return {
        "success": True,
        "data": {
            "table": _table_public(table, list(persisted_columns), int(row_count)),
            "message": "created",
        },
    }


@router.get("/table/{table_id}")
async def get_table(
    table_id: str,
    request: Request,
    workspaceId: str = "lingxi",
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace, table = await _table_for_id(request, table_id, context)
    async with service_of(request).db.session() as session:
        cols = (
            (
                await session.execute(
                    select(WorkspaceTableColumn).where(WorkspaceTableColumn.table_id == table.id)
                )
            )
            .scalars()
            .all()
        )
        count = (
            await session.scalar(
                select(func.count())
                .select_from(WorkspaceTableRow)
                .where(WorkspaceTableRow.table_id == table.id)
            )
            or 0
        )
    return {"success": True, "data": {"table": _table_public(table, list(cols), int(count))}}


@router.patch("/table/{table_id}")
async def update_table(
    table_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace, table = await _table_for_id(request, table_id, context)
    _assert_table_writable(table)
    async with service_of(request).db.session() as session:
        current = await session.get(WorkspaceTable, table.id)
        if current is None:
            raise not_found()
        if body.get("name") is not None:
            current.name = str(body["name"]).strip()[:255]
        if isinstance(body.get("metadata"), dict):
            current.metadata_payload = dict(body["metadata"])
        if "folderId" in body:
            current.metadata_payload = {
                **(current.metadata_payload or {}),
                "folderId": body.get("folderId") or None,
            }
        if isinstance(body.get("locks"), dict):
            existing_locks: dict[str, Any] = (
                dict((current.metadata_payload or {}).get("locks") or {})
                if isinstance((current.metadata_payload or {}).get("locks"), dict)
                else {}
            )
            current.metadata_payload = {
                **(current.metadata_payload or {}),
                "locks": {
                    **existing_locks,
                    **{
                        key: bool(value)
                        for key, value in body["locks"].items()
                        if key in {"schemaLocked", "insertLocked", "updateLocked", "deleteLocked"}
                    },
                },
            }
        await session.commit()
        cols = (
            (
                await session.execute(
                    select(WorkspaceTableColumn).where(WorkspaceTableColumn.table_id == current.id)
                )
            )
            .scalars()
            .all()
        )
        count = (
            await session.scalar(
                select(func.count())
                .select_from(WorkspaceTableRow)
                .where(WorkspaceTableRow.table_id == current.id)
            )
            or 0
        )
        table = current
    return {"success": True, "data": {"table": _table_public(table, list(cols), int(count))}}


@router.delete("/table/{table_id}")
async def archive_table(
    table_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    _assert_table_writable(table)
    async with service_of(request).db.session() as session:
        current = await session.get(WorkspaceTable, table.id)
        if current is not None:
            current.archived = True
            await session.commit()
    return {"success": True, "data": {"message": "archived"}}


@router.post("/table/{table_id}/restore")
async def restore_table(
    table_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    _assert_table_writable(table)
    async with service_of(request).db.session() as session:
        current = await session.get(WorkspaceTable, table.id)
        if current is not None:
            current.archived = False
            await session.commit()
    async with service_of(request).db.session() as session:
        current = await session.get(WorkspaceTable, table.id)
        cols = (
            (
                await session.execute(
                    select(WorkspaceTableColumn).where(WorkspaceTableColumn.table_id == table.id)
                )
            )
            .scalars()
            .all()
        )
        count = (
            await session.scalar(
                select(func.count())
                .select_from(WorkspaceTableRow)
                .where(WorkspaceTableRow.table_id == table.id)
            )
            or 0
        )
    return {
        "success": True,
        "data": {"table": _table_public(current or table, list(cols), int(count))},
    }


@router.get("/table/{table_id}/rows")
async def list_rows(
    table_id: str,
    request: Request,
    offset: int = 0,
    limit: int = 100,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    async with service_of(request).db.session() as session:
        rows = (
            (
                await session.execute(
                    select(WorkspaceTableRow)
                    .where(WorkspaceTableRow.table_id == table.id)
                    .order_by(WorkspaceTableRow.position)
                    .offset(max(0, offset))
                    .limit(min(1000, max(1, limit)))
                )
            )
            .scalars()
            .all()
        )
        count = (
            await session.scalar(
                select(func.count())
                .select_from(WorkspaceTableRow)
                .where(WorkspaceTableRow.table_id == table.id)
            )
            or 0
        )
    public = [_table_row_public(row) for row in rows]
    return {
        "success": True,
        "data": {
            "rows": public,
            "rowCount": len(public),
            "totalCount": int(count),
            "limit": limit,
            "offset": offset,
            "nextCursor": None,
        },
    }


@router.get("/table/{table_id}/query")
async def query_rows(
    table_id: str,
    request: Request,
    q: str = "",
    offset: int = 0,
    limit: int = 100,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    needle = q.casefold().strip()
    async with service_of(request).db.session() as session:
        rows = (
            (
                await session.execute(
                    select(WorkspaceTableRow)
                    .where(WorkspaceTableRow.table_id == table.id)
                    .order_by(WorkspaceTableRow.position)
                )
            )
            .scalars()
            .all()
        )
    if needle:
        rows = [
            row
            for row in rows
            if needle in json.dumps(row.values or {}, ensure_ascii=False).casefold()
        ]
    selected = rows[max(0, offset) : max(0, offset) + min(max(1, limit), 1000)]
    public = [_table_row_public(row) for row in selected]
    return {
        "success": True,
        "data": {
            "rows": public,
            "rowCount": len(public),
            "totalCount": len(rows),
            "nextCursor": None,
        },
    }


@router.get("/table/{table_id}/rows/find")
async def find_rows(
    table_id: str,
    request: Request,
    q: str = "",
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """Compatibility projection for the grid's cell-navigation search.

    Lingxi tables are backed by the same row store as the query endpoint; this
    route returns only the cell matches expected by the grid and deliberately
    has no workflow-run semantics.
    """
    _workspace_row, table = await _table_for_id(request, table_id, context)
    needle = q.casefold().strip()
    async with service_of(request).db.session() as session:
        rows = (
            (
                await session.execute(
                    select(WorkspaceTableRow)
                    .where(WorkspaceTableRow.table_id == table.id)
                    .order_by(WorkspaceTableRow.position)
                )
            )
            .scalars()
            .all()
        )
    matches: list[dict[str, Any]] = []
    if needle:
        for ordinal, row in enumerate(rows):
            for column, value in (row.values or {}).items():
                if needle in json.dumps(value, ensure_ascii=False).casefold():
                    matches.append({"ordinal": ordinal, "rowId": row.id, "column": str(column)})
    return {"success": True, "data": {"matches": matches, "truncated": False}}


@router.get("/table/{table_id}/export")
async def export_table(
    table_id: str,
    request: Request,
    format: str = "csv",
    context: LearnerContext = Depends(current_learner_context),
) -> StreamingResponse:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    async with service_of(request).db.session() as session:
        columns = (
            (
                await session.execute(
                    select(WorkspaceTableColumn)
                    .where(WorkspaceTableColumn.table_id == table.id)
                    .order_by(WorkspaceTableColumn.position)
                )
            )
            .scalars()
            .all()
        )
        rows = (
            (
                await session.execute(
                    select(WorkspaceTableRow)
                    .where(WorkspaceTableRow.table_id == table.id)
                    .order_by(WorkspaceTableRow.position)
                )
            )
            .scalars()
            .all()
        )
    headers = [column.key for column in columns]
    if format.lower() == "json":
        return StreamingResponse(
            iter([json.dumps([row.values or {} for row in rows], ensure_ascii=False)]),
            media_type="application/json",
        )
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers)
    writer.writeheader()
    for row in rows:
        writer.writerow({header: (row.values or {}).get(header) for header in headers})
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={table.name}.csv"},
    )


@router.get("/table/{table_id}/export/download")
async def download_table_export(
    table_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> StreamingResponse:
    return await export_table(table_id, request, "csv", context)


def _row_input(body: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(body.get("rows"), list):
        return [dict(item) for item in body["rows"] if isinstance(item, dict)]
    value = body.get("data")
    return [dict(value)] if isinstance(value, dict) else []


async def _coerce_row_values(
    session: Any,
    table_id: str,
    values: dict[str, Any],
    *,
    enforce_required: bool = True,
) -> dict[str, Any]:
    """Coerce the seven native column types at the API boundary.

    Rows remain JSON documents in PostgreSQL/SQLite, but native Tables still
    promise predictable scalar types. Keeping this conversion in one helper
    means CSV import, row CRUD, and upsert all share the same validation.
    """

    columns = (
        (
            await session.execute(
                select(WorkspaceTableColumn).where(WorkspaceTableColumn.table_id == table_id)
            )
        )
        .scalars()
        .all()
    )
    by_key = {column.key: column for column in columns}
    normalized: dict[str, Any] = {}
    for key, raw in values.items():
        column = by_key.get(str(key))
        if column is None:
            # Keep forward-compatible JSON keys visible instead of silently
            # dropping user data; typed columns are still normalized below.
            normalized[str(key)] = raw
            continue
        if raw is None or raw == "":
            normalized[column.key] = None
            continue
        try:
            if column.type == "string":
                normalized[column.key] = str(raw)
            elif column.type in {"number", "currency"}:
                if isinstance(raw, bool):
                    raise ValueError
                number = float(raw)
                if not math.isfinite(number):
                    raise ValueError
                normalized[column.key] = (
                    int(number) if isinstance(raw, int) and not isinstance(raw, bool) else number
                )
            elif column.type == "boolean":
                if isinstance(raw, bool):
                    normalized[column.key] = raw
                elif isinstance(raw, (int, float)) and raw in {0, 1}:
                    normalized[column.key] = bool(raw)
                elif str(raw).strip().casefold() in {"true", "1", "yes", "y", "on"}:
                    normalized[column.key] = True
                elif str(raw).strip().casefold() in {"false", "0", "no", "n", "off"}:
                    normalized[column.key] = False
                else:
                    raise ValueError
            elif column.type == "date":
                value = str(raw).strip().replace("Z", "+00:00")
                try:
                    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                        normalized[column.key] = (
                            datetime.strptime(value, "%Y-%m-%d").date().isoformat()
                        )
                    else:
                        normalized[column.key] = datetime.fromisoformat(value).isoformat()
                except ValueError:
                    normalized[column.key] = datetime.strptime(value, "%Y-%m-%d").date().isoformat()
            elif column.type == "json":
                normalized[column.key] = json.loads(raw) if isinstance(raw, str) else raw
            elif column.type == "select":
                options = (column.options or {}).get("options", [])
                allowed = {
                    str(option.get("value") if isinstance(option, dict) else option)
                    for option in options
                }
                multiple = bool((column.options or {}).get("multiple", False))
                candidate = (
                    raw if multiple and isinstance(raw, list) else ([raw] if multiple else raw)
                )
                candidates = candidate if isinstance(candidate, list) else [candidate]
                if allowed and any(str(item) not in allowed for item in candidates):
                    raise ValueError
                normalized[column.key] = candidate
            else:
                raise ValueError
        except (TypeError, ValueError, json.JSONDecodeError, OverflowError) as exc:
            raise HTTPException(
                status_code=422,
                detail=f"invalid_{column.type}_value:{column.key}",
            ) from exc

    if enforce_required:
        missing = [
            column.key
            for column in columns
            if bool((column.options or {}).get("required"))
            and (
                column.key not in normalized
                or normalized[column.key] is None
                or normalized[column.key] == ""
            )
        ]
        if missing:
            raise HTTPException(status_code=422, detail=f"required_columns:{','.join(missing)}")
    return normalized


@router.post("/table/{table_id}/rows")
async def create_rows(
    table_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    _assert_table_writable(table)
    values = _row_input(body)
    async with service_of(request).db.session() as session:
        highest = (
            await session.scalar(
                select(func.max(WorkspaceTableRow.position)).where(
                    WorkspaceTableRow.table_id == table.id
                )
            )
            or -1
        )
        created = []
        for index, item in enumerate(values):
            normalized = await _coerce_row_values(session, table.id, item, enforce_required=True)
            row = WorkspaceTableRow(
                id=f"row_{uuid.uuid4().hex}",
                table_id=table.id,
                values=normalized,
                position=int(highest) + index + 1,
            )
            session.add(row)
            created.append(_table_row_public(row))
        await session.commit()
    return {
        "success": True,
        "data": {"rows": created, "row": created[0] if len(created) == 1 else None},
    }


@router.patch("/table/{table_id}/rows/{row_id}")
async def update_row(
    table_id: str,
    row_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    _assert_table_writable(table)
    async with service_of(request).db.session() as session:
        row = await session.scalar(
            select(WorkspaceTableRow).where(
                WorkspaceTableRow.id == row_id, WorkspaceTableRow.table_id == table.id
            )
        )
        if row is None:
            raise not_found()
        update = body.get("data") if isinstance(body.get("data"), dict) else body.get("values")
        if isinstance(update, dict):
            row.values = await _coerce_row_values(
                session, table.id, {**(row.values or {}), **update}, enforce_required=True
            )
        await session.commit()
        public = _table_row_public(row)
    return {"success": True, "data": {"row": public}}


@router.post("/table/{table_id}/rows/upsert")
async def upsert_rows(
    table_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    _assert_table_writable(table)
    rows = _row_input(body)
    async with service_of(request).db.session() as session:
        created: list[dict[str, Any]] = []
        for item in rows:
            item = dict(item)
            row_id = str(item.pop("id", "") or f"row_{uuid.uuid4().hex}")
            normalized = await _coerce_row_values(session, table.id, item, enforce_required=True)
            row = await session.scalar(
                select(WorkspaceTableRow).where(
                    WorkspaceTableRow.id == row_id, WorkspaceTableRow.table_id == table.id
                )
            )
            if row is None:
                highest = (
                    await session.scalar(
                        select(func.max(WorkspaceTableRow.position)).where(
                            WorkspaceTableRow.table_id == table.id
                        )
                    )
                    or -1
                )
                row = WorkspaceTableRow(
                    id=row_id, table_id=table.id, values=normalized, position=int(highest) + 1
                )
                session.add(row)
            else:
                row.values = normalized
            created.append(_table_row_public(row))
        await session.commit()
    return {"success": True, "data": {"rows": created}}


@router.delete("/table/{table_id}/rows/{row_id}")
async def delete_row(
    table_id: str,
    row_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    _assert_table_writable(table)
    async with service_of(request).db.session() as session:
        row = await session.scalar(
            select(WorkspaceTableRow).where(
                WorkspaceTableRow.id == row_id, WorkspaceTableRow.table_id == table.id
            )
        )
        if row is None:
            raise not_found()
        await session.delete(row)
        await session.commit()
    return {"success": True, "data": {}}


@router.post("/table/{table_id}/columns")
async def add_column(
    table_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    _assert_table_writable(table)
    column: dict[str, Any] = (
        body["column"] if isinstance(body.get("column"), dict) else body
    )
    ctype = str(column.get("type", "string"))
    if ctype not in ALLOWED_COLUMN_TYPES:
        raise HTTPException(status_code=422, detail="unsupported_column_type")
    async with service_of(request).db.session() as session:
        max_pos = (
            await session.scalar(
                select(func.max(WorkspaceTableColumn.position)).where(
                    WorkspaceTableColumn.table_id == table.id
                )
            )
            or -1
        )
        name = str(column.get("name") or f"column_{int(max_pos) + 2}")
        row = WorkspaceTableColumn(
            id=str(column.get("id") or f"col_{uuid.uuid4().hex}"),
            table_id=table.id,
            key=name,
            name=name,
            type=ctype,
            position=int(column.get("position", max_pos + 1)),
            options={
                k: column[k]
                for k in ("required", "unique", "options", "multiple", "currencyCode")
                if k in column
            },
        )
        session.add(row)
        await session.commit()
    return {"success": True, "data": {"columns": [_column_public(row)]}}


@router.patch("/table/{table_id}/columns")
async def update_column(
    table_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    _assert_table_writable(table)
    async with service_of(request).db.session() as session:
        query = select(WorkspaceTableColumn).where(WorkspaceTableColumn.table_id == table.id)
        if body.get("columnId"):
            query = query.where(WorkspaceTableColumn.id == body["columnId"])
        else:
            query = query.where(WorkspaceTableColumn.key == body.get("columnName"))
        row = await session.scalar(query)
        if row is None:
            raise not_found()
        updates: dict[str, Any] = (
            dict(body["updates"])
            if isinstance(body.get("updates"), dict)
            else dict(body.get("column", body))
        )
        if updates.get("name"):
            row.name = row.key = str(updates["name"])
        if updates.get("type") in ALLOWED_COLUMN_TYPES:
            row.type = str(updates["type"])
        row.options = {
            **(row.options or {}),
            **{
                k: updates[k]
                for k in ("required", "unique", "options", "multiple", "currencyCode")
                if k in updates
            },
        }
        await session.commit()
    return {"success": True, "data": {"columns": [_column_public(row)]}}


@router.delete("/table/{table_id}/columns")
async def delete_column(
    table_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    _assert_table_writable(table)
    async with service_of(request).db.session() as session:
        row = await session.scalar(
            select(WorkspaceTableColumn).where(
                WorkspaceTableColumn.table_id == table.id,
                or_(
                    WorkspaceTableColumn.id == body.get("columnId"),
                    WorkspaceTableColumn.key == body.get("columnName"),
                ),
            )
        )
        if row is None:
            raise not_found()
        await session.delete(row)
        await session.commit()
    return {"success": True, "data": {"columns": []}}


@router.get("/table/{table_id}/views")
async def list_views(
    table_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    async with service_of(request).db.session() as session:
        rows = (
            (
                await session.execute(
                    select(WorkspaceTableView).where(WorkspaceTableView.table_id == table.id)
                )
            )
            .scalars()
            .all()
        )
    return {"success": True, "data": {"views": [_view_public(row) for row in rows]}}


@router.post("/table/{table_id}/views")
async def create_view(
    table_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    row = WorkspaceTableView(
        id=f"view_{uuid.uuid4().hex}",
        table_id=table.id,
        name=str(body.get("name") or "视图"),
        config=dict(body.get("config") or body.get("view") or {}),
        created_by=context.learner_id,
    )
    async with service_of(request).db.session() as session:
        session.add(row)
        await session.commit()
    return {"success": True, "data": {"view": _view_public(row)}}


@router.patch("/table/{table_id}/views/{view_id}")
async def update_view(
    table_id: str,
    view_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    async with service_of(request).db.session() as session:
        row = await session.scalar(
            select(WorkspaceTableView).where(
                WorkspaceTableView.id == view_id, WorkspaceTableView.table_id == table.id
            )
        )
        if row is None:
            raise not_found()
        if body.get("name"):
            row.name = str(body["name"])
        if isinstance(body.get("config"), dict):
            row.config = dict(body["config"])
        if isinstance(body.get("configPatch"), dict):
            row.config = {**(row.config or {}), **body["configPatch"]}
        if "isDefault" in body:
            row.is_default = bool(body["isDefault"])
            if row.is_default:
                await session.execute(
                    update(WorkspaceTableView)
                    .where(
                        WorkspaceTableView.table_id == table.id,
                        WorkspaceTableView.id != row.id,
                    )
                    .values(is_default=False)
                )
        await session.commit()
    return {"success": True, "data": {"view": _view_public(row)}}


@router.delete("/table/{table_id}/views/{view_id}")
async def delete_view(
    table_id: str,
    view_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    async with service_of(request).db.session() as session:
        row = await session.scalar(
            select(WorkspaceTableView).where(
                WorkspaceTableView.id == view_id, WorkspaceTableView.table_id == table.id
            )
        )
        if row is None:
            raise not_found()
        await session.delete(row)
        await session.commit()
    return {"success": True, "data": {"deleted": True}}


# Knowledge ------------------------------------------------------------------


@router.get("/knowledge")
async def list_knowledge(
    request: Request,
    includeArchived: bool = False,
    scope: str = "active",
    workspaceId: str | None = None,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await service_of(request).project_agent_artifacts(context.learner_id)
    async with service_of(request).db.session() as session:
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


@router.post("/knowledge")
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
    async with service_of(request).db.session() as session:
        session.add(row)
        await session.commit()
    public = _knowledge_base_public(row)
    return {"success": True, "data": public, "knowledgeBase": public}


async def _base_for_id(request: Request, base_id: str, context: LearnerContext) -> KnowledgeBase:
    async with service_of(request).db.session() as session:
        row = await session.scalar(
            select(KnowledgeBase).where(
                KnowledgeBase.id == base_id, KnowledgeBase.learner_id == context.learner_id
            )
        )
    if row is None:
        raise not_found()
    return row


@router.get("/knowledge/search")
async def search_knowledge(
    request: Request,
    q: str = "",
    limit: int = 20,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """Search before the ``/{base_id}`` route so ``search`` is not a base id."""

    needle = q.strip().casefold()
    async with service_of(request).db.session() as session:
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


@router.get("/knowledge/{base_id}/next-available-slot")
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
    async with service_of(request).db.session() as session:
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


@router.get("/knowledge/{base_id}/tag-usage")
async def tag_usage(
    base_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with service_of(request).db.session() as session:
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


@router.get("/knowledge/{base_id}")
async def get_knowledge(
    base_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    row = await _base_for_id(request, base_id, context)
    public = _knowledge_base_public(row)
    return {"success": True, "data": public, "knowledgeBase": public}


@router.put("/knowledge/{base_id}")
@router.patch("/knowledge/{base_id}")
async def update_knowledge(
    base_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    row = await _base_for_id(request, base_id, context)
    async with service_of(request).db.session() as session:
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


@router.delete("/knowledge/{base_id}")
async def archive_knowledge(
    base_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    row = await _base_for_id(request, base_id, context)
    async with service_of(request).db.session() as session:
        current = await session.get(KnowledgeBase, row.id)
        if current is not None:
            current.archived = True
            await session.commit()
    return {"success": True, "data": {"message": "archived"}}


@router.post("/knowledge/{base_id}/restore")
async def restore_knowledge(
    base_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    row = await _base_for_id(request, base_id, context)
    async with service_of(request).db.session() as session:
        current = await session.get(KnowledgeBase, row.id)
        if current is not None:
            current.archived = False
            await session.commit()
    public = _knowledge_base_public(row)
    return {"success": True, "data": public, "knowledgeBase": public}


@router.get("/knowledge/{base_id}/documents")
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
    async with service_of(request).db.session() as session:
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


@router.get("/knowledge/{base_id}/tag-definitions")
async def list_tag_definitions(
    base_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with service_of(request).db.session() as session:
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


@router.post("/knowledge/{base_id}/tag-definitions", status_code=201)
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
    async with service_of(request).db.session() as session:
        session.add(row)
        await session.commit()
    return {"success": True, "data": _tag_public(row)}


@router.patch("/knowledge/{base_id}/tag-definitions/{tag_id}")
async def update_tag_definition(
    base_id: str,
    tag_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with service_of(request).db.session() as session:
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


@router.delete("/knowledge/{base_id}/tag-definitions/{tag_id}")
async def delete_tag_definition(
    base_id: str,
    tag_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with service_of(request).db.session() as session:
        row = await session.scalar(
            select(KnowledgeTag).where(KnowledgeTag.id == tag_id, KnowledgeTag.base_id == base_id)
        )
        if row is None:
            raise not_found()
        await session.delete(row)
        await session.commit()
    return {"success": True}


@router.get("/knowledge/{base_id}/documents/{document_id}/tag-definitions")
async def list_document_tag_definitions(
    base_id: str,
    document_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with service_of(request).db.session() as session:
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


@router.post("/knowledge/{base_id}/documents/{document_id}/tag-definitions")
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
    async with service_of(request).db.session() as session:
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


@router.delete("/knowledge/{base_id}/documents/{document_id}/tag-definitions")
async def delete_document_tag_definitions(
    base_id: str,
    document_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with service_of(request).db.session() as session:
        document = await session.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == document_id,
                KnowledgeDocument.base_id == base_id,
            )
        )
        if document is None:
            raise not_found()
        await session.execute(
                delete(KnowledgeDocumentTag).where(
                KnowledgeDocumentTag.document_id == document_id
            )
        )
        await session.commit()
    return {"success": True}


@router.post("/knowledge/{base_id}/documents/uploads", status_code=201)
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
    async with service_of(request).db.session() as session:
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
    return await create_upload_part_urls(upload_id, body, request, context)


@router.post("/knowledge/{base_id}/documents/uploads/{upload_id}/complete")
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
    async with service_of(request).db.session() as session:
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
    async with service_of(request).db.session() as session:
        row = await session.get(WorkspaceUploadSession, upload_id)
        if row is not None:
            row.status = "aborted"
            await session.commit()
    return {"data": _knowledge_upload_session_public(item, status="aborted", document=None)}


@router.post("/knowledge/{base_id}/documents")
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
    async with service_of(request).db.session() as session:
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


@router.post("/knowledge/{base_id}/documents/upsert")
async def upsert_document(
    base_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    document_id = str(body.get("documentId") or "").strip()
    name, mime, content = _parse_knowledge_document(body)
    async with service_of(request).db.session() as session:
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


@router.patch("/knowledge/{base_id}/documents")
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
    async with service_of(request).db.session() as session:
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


@router.get("/knowledge/{base_id}/documents/{document_id}")
async def get_document(
    base_id: str,
    document_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with service_of(request).db.session() as session:
        row = await session.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == document_id, KnowledgeDocument.base_id == base_id
            )
        )
    if row is None:
        raise not_found()
    public = _document_public(row)
    return {"success": True, "data": public, "document": public}


@router.get("/knowledge/{base_id}/documents/{document_id}/chunks")
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
    async with service_of(request).db.session() as session:
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


@router.post("/knowledge/{base_id}/documents/{document_id}/chunks")
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
    async with service_of(request).db.session() as session:
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


@router.get("/knowledge/{base_id}/documents/{document_id}/chunks/{chunk_id}")
async def get_chunk(
    base_id: str,
    document_id: str,
    chunk_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with service_of(request).db.session() as session:
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


@router.put("/knowledge/{base_id}/documents/{document_id}/chunks/{chunk_id}")
@router.patch("/knowledge/{base_id}/documents/{document_id}/chunks/{chunk_id}")
async def update_chunk(
    base_id: str,
    document_id: str,
    chunk_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with service_of(request).db.session() as session:
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


@router.delete("/knowledge/{base_id}/documents/{document_id}/chunks/{chunk_id}")
async def delete_chunk(
    base_id: str,
    document_id: str,
    chunk_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with service_of(request).db.session() as session:
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


@router.patch("/knowledge/{base_id}/documents/{document_id}/chunks")
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
    async with service_of(request).db.session() as session:
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


@router.put("/knowledge/{base_id}/documents/{document_id}")
@router.patch("/knowledge/{base_id}/documents/{document_id}")
async def update_document(
    base_id: str,
    document_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with service_of(request).db.session() as session:
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


@router.delete("/knowledge/{base_id}/documents/{document_id}")
async def archive_document(
    base_id: str,
    document_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with service_of(request).db.session() as session:
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


@router.post("/knowledge/{base_id}/documents/{document_id}/restore")
async def restore_document(
    base_id: str,
    document_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _base_for_id(request, base_id, context)
    async with service_of(request).db.session() as session:
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


@router.post("/skills")
async def create_skill(
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    name = str(body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="name_required")
    row = PersonalSkill(
        id=f"skill_{uuid.uuid4().hex}",
        learner_id=context.learner_id,
        name=name[:128],
        description=str(body.get("description") or ""),
        content=str(body.get("content") or ""),
        version=str(body.get("version") or "1.0.0"),
    )
    async with service_of(request).db.session() as session:
        session.add(row)
        await session.commit()
    public = _skill_public(row)
    return {"skills": [public], "skill": public, "data": public}


@router.patch("/skills/{skill_id}")
async def update_skill(
    skill_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    async with service_of(request).db.session() as session:
        row = await session.scalar(
            select(PersonalSkill).where(
                PersonalSkill.id == skill_id, PersonalSkill.learner_id == context.learner_id
            )
        )
        if row is None:
            raise not_found()
        for field in ("name", "description", "content", "version"):
            if field in body:
                setattr(row, field, str(body[field]))
        await session.commit()
    public = _skill_public(row)
    return {"skill": public, "data": public}


@router.delete("/skills/{skill_id}")
async def delete_skill(
    skill_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    async with service_of(request).db.session() as session:
        row = await session.scalar(
            select(PersonalSkill).where(
                PersonalSkill.id == skill_id, PersonalSkill.learner_id == context.learner_id
            )
        )
        if row is None:
            raise not_found()
        await session.delete(row)
        await session.commit()
    return {"success": True}


def _skill_public(row: PersonalSkill) -> dict[str, Any]:
    return {
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


# Logs -----------------------------------------------------------------------


@router.get("/logs")
async def list_logs(
    request: Request,
    workspaceId: str = "lingxi",
    limit: int = 50,
    cursor: str | None = None,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _workspace_for_id(request, workspaceId, context)
    async with service_of(request).db.session() as session:
        tasks = (
            (
                await session.execute(
                    select(AgentTask)
                    .where(
                        AgentTask.learner_id == context.learner_id, AgentTask.deleted_at.is_(None)
                    )
                    .order_by(desc(AgentTask.updated_at))
                    .limit(min(100, max(1, limit)))
                )
            )
            .scalars()
            .all()
        )
    logs = [
        {
            "id": task.id,
            "executionId": task.latest_execution_id or task.id,
            "workflowId": "lingxi-agent",
            "workflowName": "LingxiGraph · Sim runtime",
            "deploymentVersionId": None,
            "deploymentVersion": None,
            "deploymentVersionName": None,
            "executionOrigin": None,
            "level": "error" if task.status == "failed" else "info",
            "status": "completed"
            if task.status in {"completed", "partial", "handed_off"}
            else task.status,
            "duration": "0",
            "trigger": "agent-task",
            "createdAt": task.created_at.isoformat() if task.created_at else "",
            "workflow": {"id": "lingxi-agent", "name": "LingxiGraph · Sim runtime"},
            "jobTitle": task.title or None,
            "cost": {"total": 0},
            "pauseSummary": {
                "status": "awaiting_user" if task.status == "awaiting_user" else None,
                "total": 1 if task.status == "awaiting_user" else 0,
                "resumed": 0,
            },
            "hasPendingPause": task.status == "awaiting_user",
        }
        for task in tasks
    ]
    return {"success": True, "data": logs, "nextCursor": None}


@router.get("/logs/stats")
async def log_stats(
    request: Request,
    workspaceId: str = "lingxi",
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _workspace_for_id(request, workspaceId, context)
    async with service_of(request).db.session() as session:
        total = (
            await session.scalar(
                select(func.count())
                .select_from(AgentTask)
                .where(AgentTask.learner_id == context.learner_id)
            )
            or 0
        )
        failed = (
            await session.scalar(
                select(func.count())
                .select_from(AgentTask)
                .where(AgentTask.learner_id == context.learner_id, AgentTask.status == "failed")
            )
            or 0
        )
    now = datetime.now(UTC).isoformat()
    return {
        "workflows": [],
        "aggregateSegments": [],
        "totalRuns": int(total),
        "totalErrors": int(failed),
        "avgLatency": 0,
        "timeBounds": {"start": now, "end": now},
        "segmentMs": 0,
    }


@router.get("/logs/export")
async def export_logs(
    request: Request,
    format: str = "json",
    context: LearnerContext = Depends(current_learner_context),
) -> StreamingResponse:
    async with service_of(request).db.session() as session:
        tasks = (
            (
                await session.execute(
                    select(AgentTask)
                    .where(AgentTask.learner_id == context.learner_id)
                    .order_by(desc(AgentTask.updated_at))
                )
            )
            .scalars()
            .all()
        )
    records = [
        {
            "id": task.id,
            "status": task.status,
            "prompt": task.prompt,
            "createdAt": task.created_at.isoformat() if task.created_at else None,
            "updatedAt": task.updated_at.isoformat() if task.updated_at else None,
        }
        for task in tasks
    ]
    if format.lower() == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer, fieldnames=["id", "status", "prompt", "createdAt", "updatedAt"]
        )
        writer.writeheader()
        writer.writerows(records)
        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=lingxi-logs.csv"},
        )
    return StreamingResponse(
        iter([json.dumps(records, ensure_ascii=False)]), media_type="application/json"
    )


@router.get("/logs/by-execution/{execution_id}")
async def log_by_execution(
    execution_id: str,
    request: Request,
    workspaceId: str = "lingxi",
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _workspace_for_id(request, workspaceId, context)
    svc = service_of(request)
    try:
        snapshot = await svc.agent_execution_snapshot(execution_id, context.learner_id)
    except KeyError as exc:
        raise not_found() from exc
    task_id = snapshot["taskId"]
    async with svc.db.session() as session:
        events = (
            (
                await session.execute(
                    select(AgentTaskEvent)
                    .where(
                        AgentTaskEvent.task_id == task_id,
                        AgentTaskEvent.execution_id == execution_id,
                    )
                    .order_by(AgentTaskEvent.sequence)
                )
            )
            .scalars()
            .all()
        )
    metadata = snapshot["executionMetadata"]
    started_at = metadata.get("startedAt") or datetime.now(UTC).isoformat()
    detail = {
        "id": execution_id,
        "executionId": execution_id,
        "workflowId": "lingxi-agent",
        "workflowName": "LingxiGraph · Sim runtime",
        "deploymentVersionId": None,
        "deploymentVersion": None,
        "deploymentVersionName": None,
        "executionOrigin": None,
        "level": "error" if snapshot["status"] == "failed" else "info",
        "status": snapshot["status"],
        "duration": str(metadata.get("totalDurationMs") or 0),
        "trigger": metadata.get("trigger"),
        "createdAt": started_at,
        "workflow": {"id": "lingxi-agent", "name": "LingxiGraph · Sim runtime"},
        "jobTitle": None,
        "cost": {"total": 0},
        "pauseSummary": {
            "status": "awaiting_user" if snapshot["status"] == "awaiting_user" else None,
            "total": 1 if snapshot["status"] == "awaiting_user" else 0,
            "resumed": 0,
        },
        "hasPendingPause": snapshot["status"] == "awaiting_user",
        "executionData": {
            "totalDuration": metadata.get("totalDurationMs"),
            "enhanced": True,
            "traceSpans": snapshot["traceSpans"],
            "workflowInput": {"taskId": task_id},
            "trigger": metadata.get("trigger"),
        },
        "files": None,
        "events": [
            {
                "id": event.sequence,
                "sequence": event.sequence,
                "type": event.kind,
                "kind": event.kind,
                "payload": event.payload,
                "runtime": event.runtime or {},
                "createdAt": event.created_at.isoformat() if event.created_at else None,
            }
            for event in events
        ],
        "error": None,
    }
    return {"success": True, "data": detail}


@router.get("/logs/execution/{execution_id}")
async def execution_snapshot(
    execution_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        snapshot = await service_of(request).agent_execution_snapshot(
            execution_id, context.learner_id
        )
        metadata = snapshot.get("executionMetadata") or {}
        metadata["startedAt"] = metadata.get("startedAt") or datetime.now(UTC).isoformat()
        snapshot["executionMetadata"] = metadata
        return snapshot
    except KeyError as exc:
        raise not_found() from exc


@router.get("/logs/{log_id}")
async def log_detail(
    log_id: str,
    request: Request,
    workspaceId: str = "lingxi",
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _workspace_for_id(request, workspaceId, context)
    svc = service_of(request)
    async with svc.db.session() as session:
        task = await session.scalar(
            select(AgentTask).where(
                AgentTask.id == log_id, AgentTask.learner_id == context.learner_id
            )
        )
        if task is None:
            raise not_found()
        events = (
            (
                await session.execute(
                    select(AgentTaskEvent)
                    .where(AgentTaskEvent.task_id == task.id)
                    .order_by(AgentTaskEvent.sequence)
                )
            )
            .scalars()
            .all()
        )
    started_at = task.created_at.isoformat() if task.created_at else datetime.now(UTC).isoformat()
    detail = {
        "id": task.id,
        "executionId": task.latest_execution_id or task.id,
        "workflowId": "lingxi-agent",
        "workflowName": "LingxiGraph · Sim runtime",
        "deploymentVersionId": None,
        "deploymentVersion": None,
        "deploymentVersionName": None,
        "executionOrigin": None,
        "level": "error" if task.status == "failed" else "info",
        "status": task.status,
        "duration": "0",
        "trigger": "agent-task",
        "createdAt": started_at,
        "workflow": {"id": "lingxi-agent", "name": "LingxiGraph · Sim runtime"},
        "jobTitle": task.title or None,
        "cost": {"total": 0},
        "pauseSummary": {
            "status": "awaiting_user" if task.status == "awaiting_user" else None,
            "total": 1 if task.status == "awaiting_user" else 0,
            "resumed": 0,
        },
        "hasPendingPause": task.status == "awaiting_user",
        "executionData": {
            "totalDuration": 0,
            "enhanced": True,
            "traceSpans": [],
            "workflowInput": {"taskId": task.id, "prompt": task.prompt},
            "trigger": "agent-task",
        },
        "files": None,
        "events": [
            {
                "id": event.sequence,
                "sequence": event.sequence,
                "type": event.kind,
                "kind": event.kind,
                "payload": event.payload,
                "executionId": event.execution_id,
                "runtime": event.runtime or {},
                "createdAt": event.created_at.isoformat() if event.created_at else None,
            }
            for event in events
        ],
        "error": task.error or None,
    }
    return {"success": True, "data": detail}
