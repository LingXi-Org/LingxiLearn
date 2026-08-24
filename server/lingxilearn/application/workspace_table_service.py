from __future__ import annotations

from typing import Any

from ..store.models.table import WorkspaceTable
from ..store.repositories.workspace_tables import WorkspaceTableRepository
from .table_values import coerce_table_values
from .workspace_errors import WorkspaceDomainError, WorkspaceForbidden, WorkspaceResourceNotFound

ALLOWED_COLUMN_TYPES = {"string", "number", "boolean", "date", "json", "select", "currency"}


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

    async def create_rows(
        self, table: WorkspaceTable, rows: list[dict[str, Any]]
    ) -> list[Any]:
        self.assert_writable(table)
        return await self.repository.create_rows(table.id, rows, coerce_table_values)

    async def update_row(
        self, table: WorkspaceTable, row_id: str, values: dict[str, Any] | None
    ) -> Any:
        self.assert_writable(table)
        return await self.repository.update_row(table.id, row_id, values, coerce_table_values)

    async def upsert_rows(
        self, table: WorkspaceTable, rows: list[dict[str, Any]]
    ) -> list[Any]:
        self.assert_writable(table)
        return await self.repository.upsert_rows(table.id, rows, coerce_table_values)

    async def update_column(self, table: WorkspaceTable, body: dict[str, Any]) -> Any:
        self.assert_writable(table)
        row = await self.repository.update_column(table.id, body)
        if row is None:
            raise WorkspaceResourceNotFound("resource_not_found")
        return row
