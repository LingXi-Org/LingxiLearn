"""Workspace API routes split by resource family."""

from fastapi import APIRouter

from ..application.table_csv import parse_csv_rows
from .workspace_route_shared import (
    ALLOWED_COLUMN_TYPES,
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
    WorkspaceTable,
    WorkspaceTableColumn,
    WorkspaceTableRow,
    WorkspaceTableView,
    _assert_table_writable,
    _column_public,
    _table_for_id,
    _table_public,
    _table_row_public,
    _view_public,
    _workspace_for_id,
    csv,
    current_learner_context,
    datetime,
    delete,
    ensure_runtime_tables,
    func,
    io,
    json,
    math,
    not_found,
    or_,
    re,
    select,
    services_of,
    update,
    uuid,
)

router = APIRouter(prefix="/api")


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
    table = WorkspaceTable(
        id=f"table_{uuid.uuid4().hex}",
        workspace_id=workspace.id,
        name=str(body.get("name") or "CSV 表格"),
        description="",
        metadata_payload={},
    )
    async with services_of(request).db.session() as session:
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


@router.post("/table/{table_id}/import", response_model=TableImportRowsResponse)
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
        async with services_of(request).db.session() as session:
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
    async with services_of(request).db.session() as session:
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
    async with services_of(request).db.session() as session:
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
    async with services_of(request).db.session() as session:
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


@router.get("/table/{table_id}", response_model=TableResponse)
async def get_table(
    table_id: str,
    request: Request,
    workspaceId: str = "lingxi",
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace, table = await _table_for_id(request, table_id, context)
    async with services_of(request).db.session() as session:
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


@router.patch("/table/{table_id}", response_model=TableResponse)
async def update_table(
    table_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace, table = await _table_for_id(request, table_id, context)
    _assert_table_writable(table)
    async with services_of(request).db.session() as session:
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


@router.delete("/table/{table_id}", response_model=TableMessageResponse)
async def archive_table(
    table_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    _assert_table_writable(table)
    async with services_of(request).db.session() as session:
        current = await session.get(WorkspaceTable, table.id)
        if current is not None:
            current.archived = True
            await session.commit()
    return {"success": True, "data": {"message": "archived"}}


@router.post("/table/{table_id}/restore", response_model=TableResponse)
async def restore_table(
    table_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    _assert_table_writable(table)
    async with services_of(request).db.session() as session:
        current = await session.get(WorkspaceTable, table.id)
        if current is not None:
            current.archived = False
            await session.commit()
    async with services_of(request).db.session() as session:
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


@router.get("/table/{table_id}/rows", response_model=TableRowsResponse)
async def list_rows(
    table_id: str,
    request: Request,
    offset: int = 0,
    limit: int = 100,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    async with services_of(request).db.session() as session:
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


@router.get("/table/{table_id}/query", response_model=TableRowsQueryResponse)
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
    async with services_of(request).db.session() as session:
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
    _workspace_row, table = await _table_for_id(request, table_id, context)
    needle = q.casefold().strip()
    async with services_of(request).db.session() as session:
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


async def _export_table(
    table_id: str,
    request: Request,
    format: str = "csv",
    context: LearnerContext = Depends(current_learner_context),
) -> StreamingResponse:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    async with services_of(request).db.session() as session:
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


async def _create_rows(
    table_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    _assert_table_writable(table)
    values = _row_input(body)
    async with services_of(request).db.session() as session:
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
    _workspace_row, table = await _table_for_id(request, table_id, context)
    _assert_table_writable(table)
    async with services_of(request).db.session() as session:
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


@router.post("/table/{table_id}/rows/upsert", response_model=TableRowsUpsertResponse)
async def upsert_rows(
    table_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    _assert_table_writable(table)
    rows = _row_input(body)
    async with services_of(request).db.session() as session:
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


@router.delete("/table/{table_id}/rows/{row_id}", response_model=TableEmptyDataResponse)
async def delete_row(
    table_id: str,
    row_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    _assert_table_writable(table)
    async with services_of(request).db.session() as session:
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


@router.post("/table/{table_id}/columns", response_model=TableColumnsResponse)
async def add_column(
    table_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    _assert_table_writable(table)
    column: dict[str, Any] = body["column"] if isinstance(body.get("column"), dict) else body
    ctype = str(column.get("type", "string"))
    if ctype not in ALLOWED_COLUMN_TYPES:
        raise HTTPException(status_code=422, detail="unsupported_column_type")
    async with services_of(request).db.session() as session:
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


@router.patch("/table/{table_id}/columns", response_model=TableColumnsResponse)
async def update_column(
    table_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    _assert_table_writable(table)
    async with services_of(request).db.session() as session:
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


@router.delete("/table/{table_id}/columns", response_model=TableColumnsResponse)
async def delete_column(
    table_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    _assert_table_writable(table)
    async with services_of(request).db.session() as session:
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


@router.get("/table/{table_id}/views", response_model=TableViewsResponse)
async def list_views(
    table_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    async with services_of(request).db.session() as session:
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


@router.post("/table/{table_id}/views", response_model=TableViewResponse)
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
    async with services_of(request).db.session() as session:
        session.add(row)
        await session.commit()
    return {"success": True, "data": {"view": _view_public(row)}}


@router.patch("/table/{table_id}/views/{view_id}", response_model=TableViewResponse)
async def update_view(
    table_id: str,
    view_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    async with services_of(request).db.session() as session:
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


@router.delete("/table/{table_id}/views/{view_id}", response_model=TableViewDeletedResponse)
async def delete_view(
    table_id: str,
    view_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    _workspace_row, table = await _table_for_id(request, table_id, context)
    async with services_of(request).db.session() as session:
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
