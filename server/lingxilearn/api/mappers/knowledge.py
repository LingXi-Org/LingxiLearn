"""Knowledge-base, document, chunk, tag, and upload response mapping."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .constants import PUBLIC_WORKSPACE_ID

TAG_VALUE_KEYS = (
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


def knowledge_base_response(row: Any, document_count: int = 0) -> dict[str, Any]:
    return {
        "id": row.id,
        "userId": row.learner_id,
        "name": row.name,
        "description": row.description,
        "workspaceId": PUBLIC_WORKSPACE_ID,
        "documentCount": document_count,
        "docCount": document_count,
        "fileCount": document_count,
        "tokenCount": 0,
        "chunkingConfig": {"maxSize": 1200, "minSize": 1, "overlap": 0, "strategy": "text"},
        "folderId": None,
        "deletedAt": row.updated_at.isoformat() if row.archived and row.updated_at else None,
        "archived": row.archived,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def document_tag_values(row: Any) -> dict[str, Any]:
    metadata = dict(row.metadata_payload or {})
    return {key: metadata.get(key) for key in TAG_VALUE_KEYS}


def document_response(row: Any) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    chunk_count = max(1, (len(row.content) + 1199) // 1200) if row.content else 0
    metadata = dict(row.metadata_payload or {})
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
        "uploadedAt": row.created_at.isoformat() if row.created_at else now,
        "content": row.content,
        "size": len(row.content.encode("utf-8")),
        "status": "archived" if row.archived else "ready",
        "archived": row.archived,
        "metadata": metadata,
        "readOnly": bool(metadata.get("readOnly")),
        **document_tag_values(row),
        "connectorId": metadata.get("connectorId"),
        "connectorType": metadata.get("connectorType"),
        "sourceUrl": metadata.get("sourceUrl"),
        "createdAt": row.created_at.isoformat() if row.created_at else now,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else now,
    }


def chunk_response(
    row: Any,
    *,
    document_created_at: datetime | None = None,
    document_updated_at: datetime | None = None,
    start_offset: int = 0,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    metadata = dict(row.metadata_payload or {})
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
        **{key: metadata.get(key) for key in TAG_VALUE_KEYS},
        "createdAt": (document_created_at or now).isoformat(),
        "updatedAt": (document_updated_at or document_created_at or now).isoformat(),
    }


def tag_response(row: Any, fallback_slot: str = "") -> dict[str, Any]:
    slot = row.tag_slot or fallback_slot or row.id
    now = datetime.now(UTC).isoformat()
    return {
        "id": row.id,
        "tagSlot": slot,
        "displayName": row.name,
        "name": row.name,
        "fieldType": row.field_type,
        "createdAt": now,
        "updatedAt": now,
    }


def knowledge_upload_session_response(
    item: dict[str, Any], *, status: str, document: dict[str, Any] | None
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
