"""Small HTTP helpers shared by workspace domain routers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

from fastapi import HTTPException, Request

from ..application.document_parser import KnowledgeDocumentParser
from ..application.workspace_errors import WorkspaceDomainError
from ..application.workspace_files import WorkspaceFileStorage, safe_leaf_name, validated_mime_type
from ..learner import LearnerContext
from .dependencies import services_of

MAX_FILE_SIZE = 20 * 1024 * 1024


def _raise_http(error: WorkspaceDomainError) -> NoReturn:
    raise HTTPException(status_code=error.status_code, detail=error.code) from error


def _safe_name(value: str, fallback: str = "untitled") -> str:
    try:
        return safe_leaf_name(value, fallback)
    except WorkspaceDomainError as error:
        _raise_http(error)


def _mime_type(name: str, supplied: Any) -> str:
    try:
        return validated_mime_type(name, supplied)
    except WorkspaceDomainError as error:
        _raise_http(error)


def _storage_root(request: Request, learner_id: str) -> Path:
    return WorkspaceFileStorage(services_of(request).settings.var_dir).root(learner_id)


def _parse_knowledge_document(body: dict[str, Any]) -> tuple[str, str, str]:
    try:
        return KnowledgeDocumentParser(MAX_FILE_SIZE).parse(body)
    except WorkspaceDomainError as error:
        _raise_http(error)


def _utc_datetime(value: datetime | None) -> datetime | None:
    """Normalize SQLite's naive ``DateTime(timezone=True)`` values to UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def _workspace(request: Request, context: LearnerContext) -> Any:
    return await services_of(request).workspaces.resolve(context.learner_id)


async def _workspace_for_id(
    request: Request, workspace_id: str, context: LearnerContext
) -> Any:
    try:
        return await services_of(request).workspaces.resolve(
            context.learner_id, workspace_id
        )
    except WorkspaceDomainError as error:
        _raise_http(error)


def _public_origin(request: Request) -> str:
    """Return the browser-visible origin when FastAPI is behind Next's proxy."""

    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    proto = request.headers.get("x-forwarded-proto", "http").split(",", 1)[0].strip()
    if host:
        return f"{proto}://{host}".rstrip("/")
    return str(request.base_url).rstrip("/")
