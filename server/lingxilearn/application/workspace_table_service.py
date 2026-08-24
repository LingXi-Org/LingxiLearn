from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ..store.models.table import WorkspaceTable, WorkspaceTableRow
from ..store.repositories.workspace_tables import WorkspaceTableRepository
from .table_csv import csv_download_headers, render_table_export
from .table_values import coerce_table_values
from .workspace_errors import WorkspaceDomainError, WorkspaceForbidden, WorkspaceResourceNotFound

ALLOWED_COLUMN_TYPES = {"string", "number", "boolean", "date", "json", "select", "currency"}


@dataclass(frozen=True)
class TableRowsProjection:
    rows: list[WorkspaceTableRow]
    total_count: int


@dataclass(frozen=True)
class TableExport:
    content: str
    media_type: str
    headers: dict[str, str]


class WorkspaceTableService:
    def __init__(self, db: Any) -> None:
        self.repository = WorkspaceTableRepository(db)

    async def require(self, workspace_id: str, table_id: str) -> WorkspaceTable:
        table = await self.repository.find(workspace_id, table_id)
        if table is None:
            raise WorkspaceResourceNotFound("resource_not_found")
        return table

    @staticmethod
    def assert_writable(table: WorkspaceTable) -> None:
        if (table.metadata_payload or {}).get("source") == "lingxi-runtime":
            raise WorkspaceForbidden("learning_records_are_read_only")

    @staticmethod
    def validate_columns(columns: list[dict[str, Any]]) -> None:
        if not columns:
            raise WorkspaceDomainError("at_least_one_column_required")
        if any(str(column.get("type", "string")) not in ALLOWED_COLUMN_TYPES for column in columns):
            raise WorkspaceDomainError("unsupported_column_type")

    async def create(self, workspace_id: str, body: dict[str, Any]) -> tuple[Any, list[Any], int]:
        columns = list((body.get("schema") or {}).get("columns") or [])
        self.validate_columns(columns)
        return await self.repository.create(
            workspace_id,
            str(body.get("name") or "新表格"),
            str(body.get("description") or ""),
            {"folderId": body.get("folderId") or None},
            columns,
            int(body.get("initialRowCount", 0) or 0),
        )

    async def add_column(self, table: WorkspaceTable, body: dict[str, Any]) -> Any:
        self.assert_writable(table)
        column = body["column"] if isinstance(body.get("column"), dict) else body
        self.validate_columns([column])
        return await self.repository.add_column(table.id, column)

    async def replace_rows(self, table: WorkspaceTable, rows: list[dict[str, Any]]) -> None:
        self.assert_writable(table)
        await self.repository.replace_rows(table.id, rows, coerce_table_values)

    async def create_rows(self, table: WorkspaceTable, rows: list[dict[str, Any]]) -> list[Any]:
        self.assert_writable(table)
        return await self.repository.create_rows(table.id, rows, coerce_table_values)

    async def update_row(
        self, table: WorkspaceTable, row_id: str, values: dict[str, Any] | None
    ) -> Any:
        self.assert_writable(table)
        return await self.repository.update_row(table.id, row_id, values, coerce_table_values)

    async def upsert_rows(self, table: WorkspaceTable, rows: list[dict[str, Any]]) -> list[Any]:
        self.assert_writable(table)
        return await self.repository.upsert_rows(table.id, rows, coerce_table_values)

    async def update_column(self, table: WorkspaceTable, body: dict[str, Any]) -> Any:
        self.assert_writable(table)
        row = await self.repository.update_column(table.id, body)
        if row is None:
            raise WorkspaceResourceNotFound("resource_not_found")
        return row

    async def query_rows(
        self, table: WorkspaceTable, query: str, offset: int, limit: int
    ) -> TableRowsProjection:
        rows, _count = await self.repository.rows(table.id)
        needle = query.casefold().strip()
        if needle:
            rows = [
                row
                for row in rows
                if needle in json.dumps(row.values or {}, ensure_ascii=False).casefold()
            ]
        start = max(0, offset)
        selected = rows[start : start + min(max(1, limit), 1000)]
        return TableRowsProjection(rows=list(selected), total_count=len(rows))

    async def find_cells(self, table: WorkspaceTable, query: str) -> list[dict[str, Any]]:
        needle = query.casefold().strip()
        if not needle:
            return []
        rows, _count = await self.repository.rows(table.id)
        return [
            {"ordinal": ordinal, "rowId": row.id, "column": str(column)}
            for ordinal, row in enumerate(rows)
            for column, value in (row.values or {}).items()
            if needle in json.dumps(value, ensure_ascii=False).casefold()
        ]

    async def export(self, table: WorkspaceTable, export_format: str) -> TableExport:
        columns = await self.repository.columns(table.id)
        rows, _count = await self.repository.rows(table.id)
        content, media_type = render_table_export(
            [column.key for column in columns],
            [row.values or {} for row in rows],
            export_format,
        )
        headers = csv_download_headers(f"{table.name}.csv") if media_type == "text/csv" else {}
        return TableExport(content=content, media_type=media_type, headers=headers)
