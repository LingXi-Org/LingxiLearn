"""Workspace API routes split by resource family."""

from fastapi import APIRouter

from ..application.uploads import multipart_part_urls
from ..application.workspace_errors import WorkspaceDomainError
from .workspace_route_shared import (
    MAX_FILE_SIZE,
    UTC,
    Any,
    CreateUploadResponse,
    Depends,
    FileDownloadUrlResponse,
    FileResponse,
    FolderArchiveResponse,
    FolderRestoreResponse,
    HTTPException,
    LearnerContext,
    MoveItemsResponse,
    Path,
    Query,
    Request,
    Response,
    StorageStatusResponse,
    StreamingResponse,
    SuccessResponse,
    UploadPartsResponse,
    UploadStateResponse,
    UsageLimitsResponse,
    Workspace,
    WorkspaceFile,
    WorkspaceFileContentResponse,
    WorkspaceFileResponse,
    WorkspaceFilesResponse,
    WorkspaceFolder,
    WorkspaceFolderResponse,
    WorkspaceFoldersResponse,
    WorkspaceUploadSession,
    _file_public,
    _folder_public,
    _mime_type,
    _public_origin,
    _safe_name,
    _storage_root,
    _storage_target,
    _workspace,
    _workspace_for_id,
    base64,
    binascii,
    current_learner_context,
    datetime,
    func,
    hashlib,
    io,
    not_found,
    secrets,
    select,
    services_of,
    timedelta,
    uuid,
    zipfile,
)

router = APIRouter(prefix="/api")


@router.get("/workspaces/{workspace_id}/files/folders", response_model=WorkspaceFoldersResponse)
@router.get("/workspaces/{workspace_id}/folders", response_model=WorkspaceFoldersResponse)
async def list_folders(
    workspace_id: str,
    request: Request,
    scope: str = Query("active"),
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    async with services_of(request).db.session() as session:
        query = select(WorkspaceFolder).where(WorkspaceFolder.workspace_id == workspace.id)
        if scope in {"active", "archived"}:
            query = query.where(WorkspaceFolder.archived.is_(scope == "archived"))
        rows = (await session.execute(query.order_by(WorkspaceFolder.created_at))).scalars().all()
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
    folder = WorkspaceFolder(
        id=f"folder_{uuid.uuid4().hex}",
        workspace_id=workspace.id,
        parent_id=body.get("parentId"),
        name=_safe_name(str(body.get("name") or "新文件夹")),
    )
    async with services_of(request).db.session() as session:
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
    async with services_of(request).db.session() as session:
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
    async with services_of(request).db.session() as session:
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


@router.post("/workspaces/{workspace_id}/files/move", response_model=MoveItemsResponse)
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
    async with services_of(request).db.session() as session:
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


@router.post("/workspaces/{workspace_id}/files/bulk-archive", response_model=FolderArchiveResponse)
async def bulk_archive_file_items(
    workspace_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    file_ids = {str(item) for item in body.get("fileIds") or []}
    root_folder_ids = {str(item) for item in body.get("folderIds") or []}
    async with services_of(request).db.session() as session:
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
    async with services_of(request).db.session() as session:
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
    async with services_of(request).db.session() as session:
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
    async with services_of(request).db.session() as session:
        query = select(WorkspaceFile).where(WorkspaceFile.workspace_id == workspace.id)
        query = query.where(WorkspaceFile.archived == (scope == "archived"))
        if folderId is not None:
            query = query.where(WorkspaceFile.folder_id == folderId)
        rows = (
            (await session.execute(query.order_by(WorkspaceFile.updated_at.desc()))).scalars().all()
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
        async with services_of(request).db.session() as session:
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
    async with services_of(request).db.session() as session:
        session.add(row)
        await session.commit()
    return {"success": True, "file": _file_public(row, workspace.id)}


async def _file_for_id(
    request: Request, workspace_id: str, file_id: str, context: LearnerContext
) -> tuple[Workspace, WorkspaceFile]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    async with services_of(request).db.session() as session:
        row = await session.scalar(
            select(WorkspaceFile).where(
                WorkspaceFile.id == file_id, WorkspaceFile.workspace_id == workspace.id
            )
        )
        if row is None:
            raise not_found()
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
    async with services_of(request).db.session() as session:
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
    async with services_of(request).db.session() as session:
        current = await session.get(WorkspaceFile, row.id)
        if current is not None:
            current.width, current.height = width, height
            await session.commit()
    return {"success": True}


@router.delete("/workspaces/{workspace_id}/files/{file_id}", response_model=SuccessResponse)
async def delete_file(
    workspace_id: str,
    file_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, row = await _file_for_id(request, workspace_id, file_id, context)
    async with services_of(request).db.session() as session:
        current = await session.get(WorkspaceFile, row.id)
        if current is not None:
            current.archived = True
            await session.commit()
    return {"success": True}


@router.post("/workspaces/{workspace_id}/files/{file_id}/restore", response_model=SuccessResponse)
async def restore_file(
    workspace_id: str,
    file_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, row = await _file_for_id(request, workspace_id, file_id, context)
    async with services_of(request).db.session() as session:
        current = await session.get(WorkspaceFile, row.id)
        if current is not None:
            current.archived = False
            await session.commit()
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
    async with services_of(request).db.session() as session:
        current = await session.get(WorkspaceFile, row.id)
        if current is None:
            raise not_found()
        current.size = len(raw)
        current.storage_key = storage_key
        await session.commit()
        row = current
    old_target.unlink(missing_ok=True)
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
    async with services_of(request).db.session() as session:
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
    async with services_of(request).db.session() as session:
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
    async with services_of(request).db.session() as session:
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
    temp = _storage_root(request, context.learner_id) / f".{upload_id}.part"
    workspace = await _workspace_for_id(request, str(body.get("workspaceId", "lingxi")), context)
    expires = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    async with services_of(request).db.session() as session:
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
    async with services_of(request).db.session() as session:
        row = await session.get(WorkspaceUploadSession, upload_id)
        if row is not None:
            row.status = "uploaded"
            await session.commit()
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
            _upload_sessions.get(upload_id),
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


@router.post("/files/uploads/{upload_id}/complete", response_model=UploadStateResponse)
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
        async with services_of(request).db.session() as session:
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
    async with services_of(request).db.session() as session:
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


@router.delete("/files/uploads/{upload_id}", response_model=UploadStateResponse)
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
    async with services_of(request).db.session() as session:
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
