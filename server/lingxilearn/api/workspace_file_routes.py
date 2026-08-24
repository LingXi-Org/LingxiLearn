"""Workspace API routes split by resource family."""

import base64
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse

from ..application.uploads import multipart_part_urls, upload_sessions
from ..application.workspace_errors import WorkspaceDomainError
from ..application.workspace_file_service import WorkspaceFileService
from ..application.workspace_files import (
    MAX_FILE_SIZE,
    WorkspaceFileStorage,
    safe_leaf_name,
    validated_mime_type,
)
from ..contracts.rest_models import (
    CreateUploadResponse,
    FileDownloadUrlResponse,
    FolderArchiveResponse,
    FolderRestoreResponse,
    MoveItemsResponse,
    StorageStatusResponse,
    SuccessResponse,
    UploadPartsResponse,
    UploadStateResponse,
    UsageLimitsResponse,
    WorkspaceFileContentResponse,
    WorkspaceFileResponse,
    WorkspaceFilesResponse,
    WorkspaceFolderResponse,
    WorkspaceFoldersResponse,
)
from ..learner import LearnerContext
from .dependencies import current_learner_context, not_found, services_of
from .mappers.files import file_response as _file_public
from .mappers.workspaces import folder_response as _folder_public
from .workspace_route_shared import (
    _public_origin,
    _workspace,
    _workspace_for_id,
)

router = APIRouter(prefix="/api")


def _safe_name(value: str, fallback: str = "untitled") -> str:
    try:
        return safe_leaf_name(value, fallback)
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error


def _mime_type(name: str, supplied: Any) -> str:
    try:
        return validated_mime_type(name, supplied)
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error


@router.get("/workspaces/{workspace_id}/files/folders", response_model=WorkspaceFoldersResponse)
@router.get("/workspaces/{workspace_id}/folders", response_model=WorkspaceFoldersResponse)
async def list_folders(
    workspace_id: str,
    request: Request,
    scope: str = Query("active"),
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    rows = await services_of(request).workspace_files.repository.list_folders(
        workspace.id, scope
    )
    folders = [_folder_public(row, workspace.id) for row in rows]
    return {"success": True, "folders": folders, "data": folders}


@router.post(
    "/workspaces/{workspace_id}/files/folders",
    status_code=201,
    response_model=WorkspaceFolderResponse,
)
@router.post(
    "/workspaces/{workspace_id}/folders", status_code=201, response_model=WorkspaceFolderResponse
)
async def create_folder(
    workspace_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    try:
        folder = await services_of(request).workspace_files.create_folder(
            workspace.id, body
        )
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return {"success": True, "folder": _folder_public(folder, workspace.id)}


@router.patch(
    "/workspaces/{workspace_id}/files/folders/{folder_id}", response_model=WorkspaceFolderResponse
)
@router.patch(
    "/workspaces/{workspace_id}/folders/{folder_id}", response_model=WorkspaceFolderResponse
)
async def update_folder(
    workspace_id: str,
    folder_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    try:
        folder = await services_of(request).workspace_files.update_folder(
            workspace.id, folder_id, body
        )
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    result = _folder_public(folder, workspace.id)
    return {"success": True, "folder": result}


@router.delete(
    "/workspaces/{workspace_id}/files/folders/{folder_id}", response_model=FolderArchiveResponse
)
@router.delete(
    "/workspaces/{workspace_id}/folders/{folder_id}", response_model=FolderArchiveResponse
)
async def archive_folder(
    workspace_id: str,
    folder_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    try:
        archived_folders, archived_files = await WorkspaceFileService(
            services_of(request).db
        ).archive_folder(workspace.id, folder_id)
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return {
        "success": True,
        "deletedItems": {"folders": archived_folders, "files": archived_files},
    }


@router.post("/workspaces/{workspace_id}/files/move", response_model=MoveItemsResponse)
async def move_file_items(
    workspace_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    try:
        file_count, folder_count = await services_of(request).workspace_files.move_items(
            workspace.id, body
        )
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return {"success": True, "movedItems": {"files": file_count, "folders": folder_count}}


@router.post("/workspaces/{workspace_id}/files/bulk-archive", response_model=FolderArchiveResponse)
async def bulk_archive_file_items(
    workspace_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    try:
        archived_folders, archived_files = await WorkspaceFileService(
            services_of(request).db
        ).bulk_archive(workspace.id, body)
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return {"success": True, "deletedItems": {"folders": archived_folders, "files": archived_files}}


@router.post(
    "/workspaces/{workspace_id}/files/folders/{folder_id}/restore",
    response_model=FolderRestoreResponse,
)
@router.post(
    "/workspaces/{workspace_id}/folders/{folder_id}/restore", response_model=FolderRestoreResponse
)
async def restore_folder(
    workspace_id: str,
    folder_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    try:
        folder, restored_folders, restored_files = await WorkspaceFileService(
            services_of(request).db
        ).restore_folder(workspace.id, folder_id)
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return {
        "success": True,
        "folder": _folder_public(folder, workspace.id),
        "restoredItems": {"folders": restored_folders, "files": restored_files},
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
    try:
        archive_bytes = await services_of(request).workspace_files.build_archive(
            workspace_id=workspace.id,
            learner_id=context.learner_id,
            file_ids=requested_files,
            folder_ids=requested_folders,
            var_dir=services_of(request).settings.var_dir,
        )
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return StreamingResponse(
        iter([archive_bytes]),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=lingxi-files.zip"},
    )


@router.get("/workspaces/{workspace_id}/files", response_model=WorkspaceFilesResponse)
async def list_files(
    workspace_id: str,
    request: Request,
    scope: str = Query("active"),
    folderId: str | None = None,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    if scope not in {"active", "archived"}:
        raise HTTPException(status_code=400, detail="invalid_scope")
    await services_of(request).artifacts.project_agent_artifacts(context.learner_id)
    workspace = await _workspace_for_id(request, workspace_id, context)
    rows = await services_of(request).workspace_files.repository.list_files(
        workspace.id, scope, folderId
    )
    return {"success": True, "files": [_file_public(row, workspace.id) for row in rows]}


@router.post(
    "/workspaces/{workspace_id}/files", status_code=201, response_model=WorkspaceFileResponse
)
async def create_file(
    workspace_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    try:
        raw = WorkspaceFileStorage(services_of(request).settings.var_dir).decode_content(
            body.get("content", ""), body.get("encoding")
        )
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="file_too_large")
    name = _safe_name(str(body.get("name") or body.get("fileName") or "untitled"))
    mime = _mime_type(name, body.get("type") or body.get("mimeType") or body.get("contentType"))
    folder_id = body.get("folderId") or None
    storage_key = f"{context.learner_id}/{secrets.token_urlsafe(24)}"
    WorkspaceFileStorage(services_of(request).settings.var_dir).write(
        context.learner_id, storage_key, raw
    )
    try:
        row = await services_of(request).workspace_files.create_file(
            workspace_id=workspace.id,
            folder_id=str(folder_id) if folder_id else None,
            name=name,
            mime_type=mime,
            size=len(raw),
            storage_key=storage_key,
        )
    except WorkspaceDomainError as error:
        WorkspaceFileStorage.remove(
            WorkspaceFileStorage(services_of(request).settings.var_dir).target(
                context.learner_id, storage_key
            )
        )
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return {"success": True, "file": _file_public(row, workspace.id)}


async def _file_for_id(
    request: Request, workspace_id: str, file_id: str, context: LearnerContext
) -> tuple[Any, Any]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    try:
        row = await services_of(request).workspace_files.require_file(
            workspace.id, file_id
        )
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return workspace, row


@router.get("/workspaces/{workspace_id}/files/{file_id}", response_model=WorkspaceFileResponse)
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


@router.patch("/workspaces/{workspace_id}/files/{file_id}", response_model=WorkspaceFileResponse)
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
    if "name" in body:
        row.name = _safe_name(str(body["name"]))
    if "folderId" in body:
        folder_id = body["folderId"] or None
        if folder_id:
            folder = await services_of(request).workspace_files.repository.get_folder(
                workspace.id, str(folder_id)
            )
            if folder is None or folder.archived:
                raise not_found()
        row.folder_id = folder_id
    row = await services_of(request).workspace_files.repository.save_file(row) or row
    return {"success": True, "file": _file_public(row, workspace.id)}


@router.patch(
    "/workspaces/{workspace_id}/files/{file_id}/dimensions", response_model=SuccessResponse
)
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
    row.width, row.height = width, height
    await services_of(request).workspace_files.repository.save_file(row)
    return {"success": True}


@router.delete("/workspaces/{workspace_id}/files/{file_id}", response_model=SuccessResponse)
async def delete_file(
    workspace_id: str,
    file_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, row = await _file_for_id(request, workspace_id, file_id, context)
    row.archived = True
    await services_of(request).workspace_files.repository.save_file(row)
    return {"success": True}


@router.post("/workspaces/{workspace_id}/files/{file_id}/restore", response_model=SuccessResponse)
async def restore_file(
    workspace_id: str,
    file_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, row = await _file_for_id(request, workspace_id, file_id, context)
    row.archived = False
    await services_of(request).workspace_files.repository.save_file(row)
    return {"success": True}


@router.put(
    "/workspaces/{workspace_id}/files/{file_id}/content", response_model=WorkspaceFileResponse
)
async def update_file_content(
    workspace_id: str,
    file_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        workspace = await _workspace_for_id(request, workspace_id, context)
        row = await services_of(request).workspace_files.replace_content(
            workspace_id=workspace.id,
            file_id=file_id,
            learner_id=context.learner_id,
            var_dir=services_of(request).settings.var_dir,
            content=body.get("content", ""),
            encoding=body.get("encoding"),
            max_size=MAX_FILE_SIZE,
        )
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return {"success": True, "file": _file_public(row, workspace.id)}


@router.get(
    "/workspaces/{workspace_id}/files/{file_id}/content",
    response_model=WorkspaceFileContentResponse,
)
async def get_file_content(
    workspace_id: str,
    file_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        workspace = await _workspace_for_id(request, workspace_id, context)
        row, raw = await services_of(request).workspace_files.read_content(
            workspace_id=workspace.id,
            file_id=file_id,
            learner_id=context.learner_id,
            var_dir=services_of(request).settings.var_dir,
        )
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
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
    workspace = await _workspace(request, context)
    try:
        row, target = await services_of(request).workspace_files.resolve_storage_target(
            workspace_id=workspace.id,
            learner_id=context.learner_id,
            storage_key=storage_key,
            var_dir=services_of(request).settings.var_dir,
        )
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
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
    try:
        row, target = await services_of(request).workspace_files.resolve_inline_target(
            workspace_id=workspace.id,
            learner_id=context.learner_id,
            var_dir=services_of(request).settings.var_dir,
            storage_key=key,
            file_id=fileId,
        )
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return FileResponse(target, media_type=row.mime_type, filename=row.name)


@router.post(
    "/workspaces/{workspace_id}/files/{file_id}/download", response_model=FileDownloadUrlResponse
)
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


@router.get("/files/storage-status", response_model=StorageStatusResponse)
async def storage_status() -> dict[str, bool]:
    # LingxiLearn deliberately uses its local persistent volume; no cloud
    # provider is configured or exposed by this workspace surface.
    return {"cloudConfigured": False}


@router.get("/users/me/usage-limits", response_model=UsageLimitsResponse)
async def usage_limits(
    request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    workspace = await _workspace(request, context)
    used = await services_of(request).workspace_files.repository.usage(workspace.id)
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

@router.post("/files/uploads", response_model=CreateUploadResponse)
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
    storage_root = WorkspaceFileStorage(services_of(request).settings.var_dir).root(
        context.learner_id
    )
    temp = storage_root / f".{upload_id}.part"
    workspace = await _workspace_for_id(request, str(body.get("workspaceId", "lingxi")), context)
    expires = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    await services_of(request).workspace_files.create_upload(
        upload_id=upload_id,
        workspace_id=workspace.id,
        learner_id=context.learner_id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        name=_safe_name(str(body.get("name") or "untitled")),
        mime_type=_mime_type(str(body.get("name") or "untitled"), body.get("contentType")),
        size=size,
        temp_key=str(temp.relative_to(storage_root)),
        expires_at=datetime.fromisoformat(expires),
    )
    upload_sessions[upload_id] = {
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
    item = upload_sessions.get(upload_id)
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
    WorkspaceFileStorage.write_temporary(item["temp"], raw)
    await services_of(request).workspace_files.repository.set_upload_status(
        upload_id, "uploaded"
    )
    return StreamingResponse(iter(()), status_code=204)


@router.post("/files/uploads/{upload_id}/parts", response_model=UploadPartsResponse)
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

    try:
        return multipart_part_urls(
            upload_id,
            upload_sessions.get(upload_id),
            context.learner_id,
            request.headers.get("upload-token"),
            body,
            _public_origin(request),
        )
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error


@router.put("/v2/uploads/{upload_id}/parts/{part_number}", status_code=204)
async def put_upload_part(
    upload_id: str,
    part_number: int,
    request: Request,
    token: str | None = None,
    context: LearnerContext = Depends(current_learner_context),
) -> Response:
    item = upload_sessions.get(upload_id)
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
    WorkspaceFileStorage.write_temporary(part_path, raw)
    item["parts"][part_number] = part_path
    return Response(status_code=204)


@router.post("/files/uploads/{upload_id}/complete", response_model=UploadStateResponse)
async def complete_upload(
    upload_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    item = upload_sessions.get(upload_id)
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
    raw = WorkspaceFileStorage.read_upload(item)
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
    storage_key = f"{context.learner_id}/{secrets.token_urlsafe(24)}"
    WorkspaceFileStorage(services_of(request).settings.var_dir).write(
        context.learner_id, storage_key, raw
    )
    try:
        row = await services_of(request).workspace_files.complete_upload(
            upload_id,
            workspace_id=workspace.id,
            folder_id=str(folder_id) if folder_id else None,
            name=name,
            mime_type=mime,
            size=len(raw),
            storage_key=storage_key,
            path=name,
            metadata_payload={"purpose": body.get("purpose", "workspace_file")},
        )
    except WorkspaceDomainError as error:
        WorkspaceFileStorage.remove(
            WorkspaceFileStorage(services_of(request).settings.var_dir).target(
                context.learner_id, storage_key
            )
        )
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    WorkspaceFileStorage.cleanup_upload(item)
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


@router.delete("/files/uploads/{upload_id}", response_model=UploadStateResponse)
async def abort_upload(
    upload_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    item = upload_sessions.get(upload_id)
    if (
        item is None
        or item["learner_id"] != context.learner_id
        or request.headers.get("upload-token") != item["token"]
    ):
        raise not_found()
    upload_sessions.pop(upload_id, None)
    WorkspaceFileStorage.cleanup_upload(item)
    await services_of(request).workspace_files.repository.set_upload_status(
        upload_id, "aborted"
    )
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
