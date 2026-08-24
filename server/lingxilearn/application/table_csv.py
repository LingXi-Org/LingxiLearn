from __future__ import annotations

import csv
import io
from typing import Any


def parse_csv_rows(raw: str, delimiter: str = ",") -> tuple[list[str], list[dict[str, Any]]]:
    reader = csv.DictReader(io.StringIO(raw), delimiter=delimiter)
    headers = [str(item or "column").strip() or "column" for item in (reader.fieldnames or [])]
    rows = [{key: value for key, value in row.items() if key is not None} for row in reader]
    return headers, rows
