from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import delete, func, or_, select, update

from ..models.table import (
    WorkspaceTable,
    WorkspaceTableColumn,
    WorkspaceTableRow,
    WorkspaceTableView,
)
from ..runtime_tables import ensure_runtime_tables


class WorkspaceTableRepository:
    def __init__(self, db: Any) -> None:
        self._db = db

    async def ensure_runtime_tables(self, workspace_id: str) -> None:
        async with self._db.session() as session:
            await ensure_runtime_tables(session, workspace_id)
            await session.commit()

    async def find(self, workspace_id: str, table_id: str) -> WorkspaceTable | None:
        async with self._db.session() as session:
            return await session.scalar(
                select(WorkspaceTable).where(
                    WorkspaceTable.id == table_id, WorkspaceTable.workspace_id == workspace_id
                )
            )

    async def list_with_details(
        self, workspace_id: str, scope: str, include_archived: bool | None
    ) -> list[tuple[WorkspaceTable, list[WorkspaceTableColumn], int]]:
        async with self._db.session() as session:
            query = select(WorkspaceTable).where(WorkspaceTable.workspace_id == workspace_id)
            if scope in {"active", "archived"}:
                query = query.where(WorkspaceTable.archived.is_(scope == "archived"))
            elif include_archived is False:
                query = query.where(WorkspaceTable.archived.is_(False))
            tables = list(
                (await session.execute(query.order_by(WorkspaceTable.updated_at.desc())))
                .scalars()
                .all()
            )
            result = []
            for table in tables:
                columns = list(
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
                count = await session.scalar(
                    select(func.count())
                    .select_from(WorkspaceTableRow)
                    .where(WorkspaceTableRow.table_id == table.id)
                )
                result.append((table, columns, int(count or 0)))
            return result

    async def details(
        self, table_id: str
    ) -> tuple[WorkspaceTable | None, list[WorkspaceTableColumn], int]:
        async with self._db.session() as session:
            table = await session.get(WorkspaceTable, table_id)
            columns = list(
                (
                    await session.execute(
                        select(WorkspaceTableColumn).where(
                            WorkspaceTableColumn.table_id == table_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            count = await session.scalar(
                select(func.count())
                .select_from(WorkspaceTableRow)
                .where(WorkspaceTableRow.table_id == table_id)
            )
            return table, columns, int(count or 0)

    async def create(
        self,
        workspace_id: str,
        name: str,
        description: str,
        metadata: dict[str, Any],
        columns: list[dict[str, Any]],
        initial_rows: int = 0,
    ) -> tuple[WorkspaceTable, list[WorkspaceTableColumn], int]:
        table = WorkspaceTable(
            id=f"table_{uuid.uuid4().hex}",
            workspace_id=workspace_id,
            name=name,
            description=description,
            metadata_payload=metadata,
        )
        persisted: list[WorkspaceTableColumn] = []
        async with self._db.session() as session:
            session.add(table)
            for index, column in enumerate(columns):
                column_name = str(column.get("name") or f"column_{index + 1}")
                row = WorkspaceTableColumn(
                    id=str(column.get("id") or f"col_{uuid.uuid4().hex}"),
                    table_id=table.id,
                    key=column_name,
                    name=column_name,
                    type=str(column.get("type", "string")),
                    position=int(column.get("position", index)),
                    options={
                        k: column[k]
                        for k in ("required", "unique", "options", "multiple", "currencyCode")
                        if k in column
                    },
                )
                session.add(row)
                persisted.append(row)
            for index in range(initial_rows):
                session.add(
                    WorkspaceTableRow(
                        id=f"row_{uuid.uuid4().hex}", table_id=table.id, values={}, position=index
                    )
                )
            await session.commit()
        return table, persisted, initial_rows

    async def import_csv(
        self, workspace_id: str, name: str, headers: list[str], rows: list[dict[str, Any]]
    ) -> WorkspaceTable:
        table = WorkspaceTable(
            id=f"table_{uuid.uuid4().hex}",
            workspace_id=workspace_id,
            name=name,
            description="",
            metadata_payload={},
        )
        async with self._db.session() as session:
            session.add(table)
            for position, header in enumerate(headers):
                session.add(
                    WorkspaceTableColumn(
                        id=f"col_{uuid.uuid4().hex}",
                        table_id=table.id,
                        key=header,
                        name=header,
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
        return table

    async def update_table(self, table_id: str, body: dict[str, Any]) -> WorkspaceTable | None:
        async with self._db.session() as session:
            table = await session.get(WorkspaceTable, table_id)
            if table is None:
                return None
            if body.get("name") is not None:
                table.name = str(body["name"]).strip()[:255]
            if isinstance(body.get("metadata"), dict):
                table.metadata_payload = dict(body["metadata"])
            if "folderId" in body:
                table.metadata_payload = {
                    **(table.metadata_payload or {}),
                    "folderId": body.get("folderId") or None,
                }
            if isinstance(body.get("locks"), dict):
                existing = (table.metadata_payload or {}).get("locks") or {}
                table.metadata_payload = {
                    **(table.metadata_payload or {}),
                    "locks": {
                        **existing,
                        **{
                            key: bool(value)
                            for key, value in body["locks"].items()
                            if key
                            in {"schemaLocked", "insertLocked", "updateLocked", "deleteLocked"}
                        },
                    },
                }
            await session.commit()
            return table

    async def set_archived(self, table_id: str, archived: bool) -> WorkspaceTable | None:
        async with self._db.session() as session:
            table = await session.get(WorkspaceTable, table_id)
            if table is not None:
                table.archived = archived
                await session.commit()
            return table

    async def rows(
        self, table_id: str, offset: int = 0, limit: int | None = None
    ) -> tuple[list[WorkspaceTableRow], int]:
        async with self._db.session() as session:
            query = (
                select(WorkspaceTableRow)
                .where(WorkspaceTableRow.table_id == table_id)
                .order_by(WorkspaceTableRow.position)
                .offset(max(0, offset))
            )
            if limit is not None:
                query = query.limit(min(1000, max(1, limit)))
            rows = list((await session.execute(query)).scalars().all())
            count = await session.scalar(
                select(func.count())
                .select_from(WorkspaceTableRow)
                .where(WorkspaceTableRow.table_id == table_id)
            )
            return rows, int(count or 0)

    async def columns(self, table_id: str) -> list[WorkspaceTableColumn]:
        async with self._db.session() as session:
            return list(
                (
                    await session.execute(
                        select(WorkspaceTableColumn)
                        .where(WorkspaceTableColumn.table_id == table_id)
                        .order_by(WorkspaceTableColumn.position)
                    )
                )
                .scalars()
                .all()
            )

    async def replace_rows(
        self,
        table_id: str,
        rows: list[dict[str, Any]],
        coerce: Callable[[list[Any], dict[str, Any]], dict[str, Any]],
    ) -> None:
        async with self._db.session() as session:
            columns = list(
                (
                    await session.execute(
                        select(WorkspaceTableColumn).where(
                            WorkspaceTableColumn.table_id == table_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            normalized = [coerce(columns, row) for row in rows]
            await session.execute(
                delete(WorkspaceTableRow).where(WorkspaceTableRow.table_id == table_id)
            )
            for position, values in enumerate(normalized):
                session.add(
                    WorkspaceTableRow(
                        id=f"row_{uuid.uuid4().hex}",
                        table_id=table_id,
                        values=values,
                        position=position,
                    )
                )
            await session.commit()

    async def create_rows(
        self,
        table_id: str,
        rows: list[dict[str, Any]],
        coerce: Callable[[list[Any], dict[str, Any]], dict[str, Any]],
    ) -> list[WorkspaceTableRow]:
        async with self._db.session() as session:
            columns = list(
                (
                    await session.execute(
                        select(WorkspaceTableColumn).where(
                            WorkspaceTableColumn.table_id == table_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            highest = await session.scalar(
                select(func.max(WorkspaceTableRow.position)).where(
                    WorkspaceTableRow.table_id == table_id
                )
            )
            start = int(highest if highest is not None else -1)
            created = []
            for index, values in enumerate(rows):
                row = WorkspaceTableRow(
                    id=f"row_{uuid.uuid4().hex}",
                    table_id=table_id,
                    values=coerce(columns, values),
                    position=start + index + 1,
                )
                session.add(row)
                created.append(row)
            await session.commit()
            return created

    async def update_row(
        self,
        table_id: str,
        row_id: str,
        values: dict[str, Any] | None,
        coerce: Callable[[list[Any], dict[str, Any]], dict[str, Any]],
    ) -> WorkspaceTableRow | None:
        async with self._db.session() as session:
            row = await session.scalar(
                select(WorkspaceTableRow).where(
                    WorkspaceTableRow.id == row_id, WorkspaceTableRow.table_id == table_id
                )
            )
            if row is None:
                return None
            if values is not None:
                columns = list(
                    (
                        await session.execute(
                            select(WorkspaceTableColumn).where(
                                WorkspaceTableColumn.table_id == table_id
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                row.values = coerce(columns, {**(row.values or {}), **values})
            await session.commit()
            return row

    async def upsert_rows(
        self,
        table_id: str,
        items: list[dict[str, Any]],
        coerce: Callable[[list[Any], dict[str, Any]], dict[str, Any]],
    ) -> list[WorkspaceTableRow]:
        async with self._db.session() as session:
            columns = list(
                (
                    await session.execute(
                        select(WorkspaceTableColumn).where(
                            WorkspaceTableColumn.table_id == table_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            highest = await session.scalar(
                select(func.max(WorkspaceTableRow.position)).where(
                    WorkspaceTableRow.table_id == table_id
                )
            )
            position = int(highest if highest is not None else -1)
            result = []
            for item in items:
                values = dict(item)
                row_id = str(values.pop("id", "") or f"row_{uuid.uuid4().hex}")
                normalized = coerce(columns, values)
                row = await session.scalar(
                    select(WorkspaceTableRow).where(
                        WorkspaceTableRow.id == row_id, WorkspaceTableRow.table_id == table_id
                    )
                )
                if row is None:
                    position += 1
                    row = WorkspaceTableRow(
                        id=row_id, table_id=table_id, values=normalized, position=position
                    )
                    session.add(row)
                else:
                    row.values = normalized
                result.append(row)
            await session.commit()
            return result

    async def delete_row(self, table_id: str, row_id: str) -> bool:
        async with self._db.session() as session:
            row = await session.scalar(
                select(WorkspaceTableRow).where(
                    WorkspaceTableRow.id == row_id, WorkspaceTableRow.table_id == table_id
                )
            )
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True

    async def add_column(self, table_id: str, column: dict[str, Any]) -> WorkspaceTableColumn:
        async with self._db.session() as session:
            max_pos = await session.scalar(
                select(func.max(WorkspaceTableColumn.position)).where(
                    WorkspaceTableColumn.table_id == table_id
                )
            )
            position = int(max_pos if max_pos is not None else -1)
            name = str(column.get("name") or f"column_{position + 2}")
            row = WorkspaceTableColumn(
                id=str(column.get("id") or f"col_{uuid.uuid4().hex}"),
                table_id=table_id,
                key=name,
                name=name,
                type=str(column.get("type", "string")),
                position=int(column.get("position", position + 1)),
                options={
                    k: column[k]
                    for k in ("required", "unique", "options", "multiple", "currencyCode")
                    if k in column
                },
            )
            session.add(row)
            await session.commit()
            return row

    async def update_column(
        self, table_id: str, body: dict[str, Any]
    ) -> WorkspaceTableColumn | None:
        async with self._db.session() as session:
            query = select(WorkspaceTableColumn).where(WorkspaceTableColumn.table_id == table_id)
            query = (
                query.where(WorkspaceTableColumn.id == body["columnId"])
                if body.get("columnId")
                else query.where(WorkspaceTableColumn.key == body.get("columnName"))
            )
            row = await session.scalar(query)
            if row is None:
                return None
            values = (
                dict(body["updates"])
                if isinstance(body.get("updates"), dict)
                else dict(body.get("column", body))
            )
            if values.get("name"):
                row.name = row.key = str(values["name"])
            if values.get("type") in {
                "string",
                "number",
                "boolean",
                "date",
                "json",
                "select",
                "currency",
            }:
                row.type = str(values["type"])
            row.options = {
                **(row.options or {}),
                **{
                    k: values[k]
                    for k in ("required", "unique", "options", "multiple", "currencyCode")
                    if k in values
                },
            }
            await session.commit()
            return row

    async def delete_column(self, table_id: str, column_id: Any, column_name: Any) -> bool:
        async with self._db.session() as session:
            row = await session.scalar(
                select(WorkspaceTableColumn).where(
                    WorkspaceTableColumn.table_id == table_id,
                    or_(
                        WorkspaceTableColumn.id == column_id,
                        WorkspaceTableColumn.key == column_name,
                    ),
                )
            )
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True

    async def list_views(self, table_id: str) -> list[WorkspaceTableView]:
        async with self._db.session() as session:
            return list(
                (
                    await session.execute(
                        select(WorkspaceTableView).where(WorkspaceTableView.table_id == table_id)
                    )
                )
                .scalars()
                .all()
            )

    async def create_view(
        self, table_id: str, learner_id: str, body: dict[str, Any]
    ) -> WorkspaceTableView:
        row = WorkspaceTableView(
            id=f"view_{uuid.uuid4().hex}",
            table_id=table_id,
            name=str(body.get("name") or "视图"),
            config=dict(body.get("config") or body.get("view") or {}),
            created_by=learner_id,
        )
        async with self._db.session() as session:
            session.add(row)
            await session.commit()
            return row

    async def update_view(
        self, table_id: str, view_id: str, body: dict[str, Any]
    ) -> WorkspaceTableView | None:
        async with self._db.session() as session:
            row = await session.scalar(
                select(WorkspaceTableView).where(
                    WorkspaceTableView.id == view_id, WorkspaceTableView.table_id == table_id
                )
            )
            if row is None:
                return None
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
                            WorkspaceTableView.table_id == table_id, WorkspaceTableView.id != row.id
                        )
                        .values(is_default=False)
                    )
            await session.commit()
            return row

    async def delete_view(self, table_id: str, view_id: str) -> bool:
        async with self._db.session() as session:
            row = await session.scalar(
                select(WorkspaceTableView).where(
                    WorkspaceTableView.id == view_id, WorkspaceTableView.table_id == table_id
                )
            )
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True
