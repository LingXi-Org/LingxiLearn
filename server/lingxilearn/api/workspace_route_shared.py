# ruff: noqa: F401
"""Shared imports and serializers for the domain workspace routers.

This compatibility layer is intentionally limited to constants, lookup helpers,
and public response serializers. Endpoint handlers live in sibling modules.
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
from typing import Any, NoReturn
from urllib.parse import unquote
from xml.etree import ElementTree

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import delete, desc, false, func, or_, select, update

from ..application.document_parser import KnowledgeDocumentParser
from ..application.workspace_errors import WorkspaceDomainError
from ..application.workspace_files import WorkspaceFileStorage, safe_leaf_name, validated_mime_type
from ..application.workspaces import WorkspaceService
from ..contracts.rest_models import (
    CreateUploadResponse,
    DocumentTagSaveResponse,
    FileDownloadUrlResponse,
    FolderArchiveResponse,
    FolderRestoreResponse,
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
    LearningRecordResponse,
    MessageResponse,
    MoveItemsResponse,
    PinnedItemResponse,
    PinnedItemsResponse,
    SkillCreateResponse,
    SkillUpdateResponse,
    StorageStatusResponse,
    SuccessResponse,
    TableColumnsResponse,
    TableEmptyDataResponse,
    TableImportCsvResponse,
    TableImportRowsResponse,
    TableListResponse,
    TableMessageResponse,
    TableResponse,
    TableRowResponse,
    TableRowsCreateResponse,
    TableRowsFindResponse,
    TableRowsQueryResponse,
    TableRowsResponse,
    TableRowsUpsertResponse,
    TableViewDeletedResponse,
    TableViewResponse,
    TableViewsResponse,
    UploadPartsResponse,
    UploadStateResponse,
    UsageLimitsResponse,
    WorkspaceFileContentResponse,
    WorkspaceFileResponse,
    WorkspaceFilesResponse,
    WorkspaceFolderResponse,
    WorkspaceFoldersResponse,
    WorkspaceListResponse,
    WorkspaceMembersResponse,
    WorkspacePermissionsResponse,
    WorkspaceResponse,
)
from ..learner import LearnerContext
from ..store.models.agent import AgentTask, AgentTaskEvent
from ..store.models.base import utcnow
from ..store.models.knowledge import (
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentTag,
    KnowledgeTag,
)
from ..store.models.runtime import AgentExecution
from ..store.models.workspace import (
    PersonalSkill,
    Workspace,
    WorkspaceFile,
    WorkspaceFolder,
    WorkspacePinnedItem,
    WorkspaceUploadSession,
)
from ..store.runtime_tables import (
    RUNTIME_COLUMN_LABELS,
    RUNTIME_COLUMNS_BY_CATEGORY,
    RUNTIME_STUDENT_CATEGORIES,
    RUNTIME_STUDENT_COLUMNS,
    ensure_runtime_tables,
)
from .dependencies import current_learner_context, not_found, services_of
from .mappers.files import file_response as _file_public
from .mappers.knowledge import (
    chunk_response as _chunk_public,
)
from .mappers.knowledge import (
    document_response as _document_public,
)
from .mappers.knowledge import (
    document_tag_values as _document_tag_values,
)
from .mappers.knowledge import (
    knowledge_base_response as _knowledge_base_public,
)
from .mappers.knowledge import (
    knowledge_upload_session_response as _knowledge_upload_session_public,
)
from .mappers.knowledge import (
    tag_response as _tag_public,
)
from .mappers.skills import skill_response as _skill_public
from .mappers.tables import (
    column_response as _column_public,
)
from .mappers.tables import (
    table_response as _table_public,
)
from .mappers.tables import (
    table_row_response as _table_row_public,
)
from .mappers.tables import (
    table_view_response as _view_public,
)
from .mappers.workspaces import folder_response as _folder_public
from .mappers.workspaces import pinned_item_response as _pinned_item_public
from .mappers.workspaces import workspace_response as _public_workspace

MAX_FILE_SIZE = 20 * 1024 * 1024
PINNED_RESOURCE_TYPES = {"workflow", "file", "knowledge_base", "table", "folder", "workspace"}
# Stable public alias for a learner's single personal workspace. Database IDs
# remain internal; accepting either form at the API boundary is intentional.
PUBLIC_WORKSPACE_ID = "lingxi"


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


def _storage_target(request: Request, learner_id: str, storage_key: str) -> Path:
    try:
        return WorkspaceFileStorage(services_of(request).settings.var_dir).target(
            learner_id, storage_key
        )
    except WorkspaceDomainError as error:
        _raise_http(error)


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


async def _workspace(request: Request, context: LearnerContext) -> Workspace:
    return await WorkspaceService(services_of(request).db).resolve(context.learner_id)


async def _workspace_for_id(
    request: Request, workspace_id: str, context: LearnerContext
) -> Workspace:
    try:
        return await WorkspaceService(services_of(request).db).resolve(
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
