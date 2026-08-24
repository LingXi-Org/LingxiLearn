from __future__ import annotations

import csv
import io
import json
from typing import Any
from urllib.parse import quote


def parse_csv_rows(raw: str, delimiter: str = ",") -> tuple[list[str], list[dict[str, Any]]]:
    reader = csv.DictReader(io.StringIO(raw), delimiter=delimiter)
    headers = [str(item or "column").strip() or "column" for item in (reader.fieldnames or [])]
    rows = [{key: value for key, value in row.items() if key is not None} for row in reader]
    return headers, rows


def render_table_export(
    headers: list[str], rows: list[dict[str, Any]], export_format: str
) -> tuple[str, str]:
    """Render the transport-neutral table export payload and its media type."""
    if export_format.casefold() == "json":
        return json.dumps(rows, ensure_ascii=False), "application/json"

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers)
    writer.writeheader()
    for row in rows:
        writer.writerow({header: row.get(header) for header in headers})
    return buffer.getvalue(), "text/csv"


def csv_download_headers(filename: str) -> dict[str, str]:
    """Build an RFC 5987-compatible attachment header for arbitrary table names."""
    try:
        filename.encode("latin-1")
    except UnicodeEncodeError:
        return {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    return {"Content-Disposition": f"attachment; filename={filename}"}
