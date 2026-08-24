"""Workspace API routes split by resource family."""

from fastapi import APIRouter

from ..application.table_csv import parse_csv_rows
from ..application.workspace_errors import WorkspaceDomainError
from ..application.workspace_table_service import WorkspaceTableService
from .workspace_route_shared import (
    MAX_FILE_SIZE,
    RUNTIME_STUDENT_CATEGORIES,
    Any,
    Depends,
    HTTPException,
    LearnerContext,
    LearningRecordResponse,
    Request,
    StreamingResponse,
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
    _column_public,
    _table_public,
    _table_row_public,
    _view_public,
    _workspace_for_id,
    csv,
    current_learner_context,
    io,
    json,
    not_found,
    services_of,
)

router = APIRouter(prefix="/api")


def _table_service(request: Request) -> WorkspaceTableService:
    return services_of(request).workspace_tables


async def _owned_table(request: Request, table_id: str, context: LearnerContext) -> tuple[Any, Any]:
    workspace = await _workspace_for_id(request, "lingxi", context)
    try:
        table = await _table_service(request).require(workspace.id, table_id)
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return workspace, table


def _raise_domain(error: WorkspaceDomainError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.code) from error


def _csv_payload(raw: str, delimiter: str = ",") -> tuple[list[str], list[dict[str, Any]]]:
    return parse_csv_rows(raw, delimiter)


@router.post("/table/import-csv", status_code=201, response_model=TableImportCsvResponse)
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
    table = await _table_service(request).repository.import_csv(
        workspace.id, str(body.get("name") or "CSV 表格"), headers, rows
    )
    return {
        "success": True,
        "data": {"table": {"id": table.id, "name": table.name}, "importedRows": len(rows)},
    }


@router.post("/table/{table_id}/import", response_model=TableImportRowsResponse)
async def import_table_rows(
    table_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _owned_table(request, table_id, context)
    raw = str(body.get("csv") or body.get("content") or "")
    _headers, rows = (
        _csv_payload(raw, str(body.get("delimiter") or ","))
        if raw
        else ([], body.get("rows") or [])
    )
    if body.get("mode") == "replace":
        try:
            await _table_service(request).replace_rows(
                table, [dict(row) for row in rows if isinstance(row, dict)]
            )
        except WorkspaceDomainError as error:
            _raise_domain(error)
    else:
        await _create_rows(table_id, {"rows": rows}, request, context)
    return {"success": True, "data": {"importedRows": len(rows)}}


@router.get("/table", response_model=TableListResponse)
async def list_tables(
    request: Request,
    workspaceId: str = "lingxi",
    scope: str = "active",
    includeArchived: bool | None = None,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspaceId, context)
    if scope not in {"active", "archived", "all"}:
        raise HTTPException(status_code=400, detail="invalid_scope")
    repository = _table_service(request).repository
    if workspaceId == "lingxi":
        await repository.ensure_runtime_tables(workspace.id)
    details = await repository.list_with_details(workspace.id, scope, includeArchived)
    result = [
        _table_public(table, columns, count)
        for table, columns, count in details
        if not (
            (table.metadata_payload or {}).get("source") == "lingxi-runtime"
            and (table.metadata_payload or {}).get("category") not in RUNTIME_STUDENT_CATEGORIES
        )
    ]
    return {
        "success": True,
        "data": {"tables": result, "totalCount": len(result)},
        "tables": result,
        "totalCount": len(result),
    }


@router.post("/lingxi/learning-records", response_model=LearningRecordResponse)
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
    projection = await services_of(request).agent_events.project_learning_record(
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


@router.post("/table", response_model=TableResponse)
async def create_table(
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, str(body.get("workspaceId", "lingxi")), context)
    try:
        table, persisted_columns, row_count = await _table_service(request).create(
            workspace.id, body
        )
    except WorkspaceDomainError as error:
        _raise_domain(error)
    return {
        "success": True,
        "data": {
            "table": _table_public(table, list(persisted_columns), int(row_count)),
            "message": "created",
        },
    }


@router.get("/table/{table_id}", response_model=TableResponse)
async def get_table(
    table_id: str,
    request: Request,
    workspaceId: str = "lingxi",
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace, table = await _owned_table(request, table_id, context)
    _current, cols, count = await _table_service(request).repository.details(table.id)
    return {"success": True, "data": {"table": _table_public(table, list(cols), int(count))}}


@router.patch("/table/{table_id}", response_model=TableResponse)
async def update_table(
    table_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace, table = await _owned_table(request, table_id, context)
    try:
        _table_service(request).assert_writable(table)
    except WorkspaceDomainError as error:
        _raise_domain(error)
    current = await _table_service(request).repository.update_table(table.id, body)
    if current is None:
        raise not_found()
    _persisted, cols, count = await _table_service(request).repository.details(current.id)
    table = current
    return {"success": True, "data": {"table": _table_public(table, list(cols), int(count))}}


@router.delete("/table/{table_id}", response_model=TableMessageResponse)
async def archive_table(
    table_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    _workspace_row, table = await _owned_table(request, table_id, context)
    try:
        _table_service(request).assert_writable(table)
    except WorkspaceDomainError as error:
        _raise_domain(error)
    await _table_service(request).repository.set_archived(table.id, True)
    return {"success": True, "data": {"message": "archived"}}


@router.post("/table/{table_id}/restore", response_model=TableResponse)
async def restore_table(
    table_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    _workspace_row, table = await _owned_table(request, table_id, context)
    try:
        _table_service(request).assert_writable(table)
    except WorkspaceDomainError as error:
        _raise_domain(error)
    await _table_service(request).repository.set_archived(table.id, False)
    current, cols, count = await _table_service(request).repository.details(table.id)
    return {
        "success": True,
        "data": {"table": _table_public(current or table, list(cols), int(count))},
    }


@router.get("/table/{table_id}/rows", response_model=TableRowsResponse)
async def list_rows(
    table_id: str,
    request: Request,
    offset: int = 0,
    limit: int = 100,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _owned_table(request, table_id, context)
    rows, count = await _table_service(request).repository.rows(table.id, offset, limit)
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


@router.get("/table/{table_id}/query", response_model=TableRowsQueryResponse)
async def query_rows(
    table_id: str,
    request: Request,
    q: str = "",
    offset: int = 0,
    limit: int = 100,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _owned_table(request, table_id, context)
    needle = q.casefold().strip()
    rows, _count = await _table_service(request).repository.rows(table.id)
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


@router.get("/table/{table_id}/rows/find", response_model=TableRowsFindResponse)
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
    _workspace_row, table = await _owned_table(request, table_id, context)
    needle = q.casefold().strip()
    rows, _count = await _table_service(request).repository.rows(table.id)
    matches: list[dict[str, Any]] = []
    if needle:
        for ordinal, row in enumerate(rows):
            for column, value in (row.values or {}).items():
                if needle in json.dumps(value, ensure_ascii=False).casefold():
                    matches.append({"ordinal": ordinal, "rowId": row.id, "column": str(column)})
    return {"success": True, "data": {"matches": matches, "truncated": False}}


async def _export_table(
    table_id: str,
    request: Request,
    format: str = "csv",
    context: LearnerContext = Depends(current_learner_context),
) -> StreamingResponse:
    _workspace_row, table = await _owned_table(request, table_id, context)
    columns = await _table_service(request).repository.columns(table.id)
    rows, _count = await _table_service(request).repository.rows(table.id)
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


@router.get("/table/{table_id}/export")
async def export_table(
    table_id: str,
    request: Request,
    format: str = "csv",
    context: LearnerContext = Depends(current_learner_context),
) -> StreamingResponse:
    return await _export_table(table_id, request, format, context)


@router.get("/table/{table_id}/export/download")
async def download_table_export(
    table_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> StreamingResponse:
    return await _export_table(table_id, request, "csv", context)


def _row_input(body: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(body.get("rows"), list):
        return [dict(item) for item in body["rows"] if isinstance(item, dict)]
    value = body.get("data")
    return [dict(value)] if isinstance(value, dict) else []


async def _create_rows(
    table_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _owned_table(request, table_id, context)
    try:
        rows = await _table_service(request).create_rows(table, _row_input(body))
    except WorkspaceDomainError as error:
        _raise_domain(error)
    created = [_table_row_public(row) for row in rows]
    return {
        "success": True,
        "data": {"rows": created, "row": created[0] if len(created) == 1 else None},
    }


@router.post("/table/{table_id}/rows", response_model=TableRowsCreateResponse)
async def create_rows(
    table_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    return await _create_rows(table_id, body, request, context)


@router.patch("/table/{table_id}/rows/{row_id}", response_model=TableRowResponse)
async def update_row(
    table_id: str,
    row_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _owned_table(request, table_id, context)
    try:
        values = body.get("data") if isinstance(body.get("data"), dict) else body.get("values")
        row = await _table_service(request).update_row(
            table, row_id, dict(values) if isinstance(values, dict) else None
        )
    except WorkspaceDomainError as error:
        _raise_domain(error)
    if row is None:
        raise not_found()
    public = _table_row_public(row)
    return {"success": True, "data": {"row": public}}


@router.post("/table/{table_id}/rows/upsert", response_model=TableRowsUpsertResponse)
async def upsert_rows(
    table_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _owned_table(request, table_id, context)
    try:
        persisted = await _table_service(request).upsert_rows(table, _row_input(body))
    except WorkspaceDomainError as error:
        _raise_domain(error)
    created = [_table_row_public(row) for row in persisted]
    return {"success": True, "data": {"rows": created}}


@router.delete("/table/{table_id}/rows/{row_id}", response_model=TableEmptyDataResponse)
async def delete_row(
    table_id: str,
    row_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _owned_table(request, table_id, context)
    try:
        _table_service(request).assert_writable(table)
    except WorkspaceDomainError as error:
        _raise_domain(error)
    if not await _table_service(request).repository.delete_row(table.id, row_id):
        raise not_found()
    return {"success": True, "data": {}}


@router.post("/table/{table_id}/columns", response_model=TableColumnsResponse)
async def add_column(
    table_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _owned_table(request, table_id, context)
    try:
        row = await _table_service(request).add_column(table, body)
    except WorkspaceDomainError as error:
        _raise_domain(error)
    return {"success": True, "data": {"columns": [_column_public(row)]}}


@router.patch("/table/{table_id}/columns", response_model=TableColumnsResponse)
async def update_column(
    table_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _owned_table(request, table_id, context)
    try:
        row = await _table_service(request).update_column(table, body)
    except WorkspaceDomainError as error:
        _raise_domain(error)
    return {"success": True, "data": {"columns": [_column_public(row)]}}


@router.delete("/table/{table_id}/columns", response_model=TableColumnsResponse)
async def delete_column(
    table_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _owned_table(request, table_id, context)
    try:
        _table_service(request).assert_writable(table)
    except WorkspaceDomainError as error:
        _raise_domain(error)
    if not await _table_service(request).repository.delete_column(
        table.id, body.get("columnId"), body.get("columnName")
    ):
        raise not_found()
    return {"success": True, "data": {"columns": []}}


@router.get("/table/{table_id}/views", response_model=TableViewsResponse)
async def list_views(
    table_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    _workspace_row, table = await _owned_table(request, table_id, context)
    rows = await _table_service(request).repository.list_views(table.id)
    return {"success": True, "data": {"views": [_view_public(row) for row in rows]}}


@router.post("/table/{table_id}/views", response_model=TableViewResponse)
async def create_view(
    table_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _owned_table(request, table_id, context)
    row = await _table_service(request).repository.create_view(table.id, context.learner_id, body)
    return {"success": True, "data": {"view": _view_public(row)}}


@router.patch("/table/{table_id}/views/{view_id}", response_model=TableViewResponse)
async def update_view(
    table_id: str,
    view_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _owned_table(request, table_id, context)
    row = await _table_service(request).repository.update_view(table.id, view_id, body)
    if row is None:
        raise not_found()
    return {"success": True, "data": {"view": _view_public(row)}}


@router.delete("/table/{table_id}/views/{view_id}", response_model=TableViewDeletedResponse)
async def delete_view(
    table_id: str,
    view_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _owned_table(request, table_id, context)
    if not await _table_service(request).repository.delete_view(table.id, view_id):
        raise not_found()
    return {"success": True, "data": {"deleted": True}}


# Knowledge ------------------------------------------------------------------
