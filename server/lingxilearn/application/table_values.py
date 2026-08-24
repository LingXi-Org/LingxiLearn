from __future__ import annotations

import json
import math
import re
from datetime import datetime
from typing import Any, Protocol

from .workspace_errors import WorkspaceDomainError


class TableColumnSpec(Protocol):
    key: str
    type: str
    options: dict[str, Any] | None


def coerce_table_values(
    columns: list[TableColumnSpec],
    values: dict[str, Any],
    *,
    enforce_required: bool = True,
) -> dict[str, Any]:
    by_key = {column.key: column for column in columns}
    normalized: dict[str, Any] = {}
    for key, raw in values.items():
        column = by_key.get(str(key))
        if column is None:
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
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    normalized[column.key] = datetime.strptime(value, "%Y-%m-%d").date().isoformat()
                else:
                    normalized[column.key] = datetime.fromisoformat(value).isoformat()
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
            raise WorkspaceDomainError(f"invalid_{column.type}_value:{column.key}") from exc

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
            raise WorkspaceDomainError(f"required_columns:{','.join(missing)}")
    return normalized
