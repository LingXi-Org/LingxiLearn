from __future__ import annotations

import ast
import base64
import io
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from lingxilearn.application.document_parser import KnowledgeDocumentParser
from lingxilearn.application.table_csv import (
    csv_download_headers,
    parse_csv_rows,
    render_table_export,
)
from lingxilearn.application.table_values import coerce_table_values
from lingxilearn.application.workspace_errors import (
    WorkspaceDomainError,
    WorkspacePayloadTooLarge,
    WorkspaceResourceNotFound,
)
from lingxilearn.application.workspace_files import (
    WorkspaceFileStorage,
    safe_leaf_name,
    validated_mime_type,
)


def test_workspace_file_policy_is_transport_neutral(tmp_path) -> None:
    storage = WorkspaceFileStorage(tmp_path)
    assert (
        storage.target("learner-1", "learner-1/file.txt").parent
        == (tmp_path / "workspaces" / "learner-1").resolve()
    )
    with pytest.raises(WorkspaceResourceNotFound):
        storage.target("learner-1", "learner-1/../secret")
    with pytest.raises(WorkspaceDomainError, match="invalid_file_name"):
        safe_leaf_name("../secret")
    with pytest.raises(WorkspaceDomainError, match="invalid_mime_type"):
        validated_mime_type("file.txt", "text/plain\nX-Injected: yes")


def test_workspace_file_router_cannot_own_persistence_or_orm_models() -> None:
    source = (
        Path(__file__).parents[1] / "lingxilearn" / "api" / "workspace_file_routes.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "sqlalchemy",
        "store.models",
        "session.execute",
        "session.scalar",
        "WorkspaceFile(",
        "WorkspaceFolder(",
        "WorkspaceUploadSession(",
    )
    assert not [token for token in forbidden if token in source]


def test_workspace_file_router_delegates_storage_target_resolution() -> None:
    source = (
        Path(__file__).parents[1] / "lingxilearn" / "api" / "workspace_file_routes.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "descendant_folder_ids",
        "Path(storage_key)",
        ".existing_target(",
        "._storage_target(",
    )
    assert not [token for token in forbidden if token in source]


def test_document_parser_handles_structured_formats_without_http_exceptions() -> None:
    parser = KnowledgeDocumentParser(1024 * 1024)
    assert parser.parse({"name": "data.json", "content": '{"answer":42}'})[2] == (
        '{\n  "answer": 42\n}'
    )
    encoded = base64.b64encode(b"a,b\n1,2").decode()
    assert parser.parse({"name": "data.csv", "content": encoded, "encoding": "base64"})[2] == (
        "a\tb\n1\t2"
    )

    docx = io.BytesIO()
    with zipfile.ZipFile(docx, "w") as archive:
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="urn:w"><w:p><w:t>Lingxi</w:t></w:p></w:document>',
        )
    assert (
        "Lingxi"
        in parser.parse(
            {
                "name": "note.docx",
                "content": base64.b64encode(docx.getvalue()).decode(),
                "encoding": "base64",
            }
        )[2]
    )


def test_document_parser_enforces_size_and_csv_parser_preserves_rows() -> None:
    with pytest.raises(WorkspacePayloadTooLarge, match="document_too_large"):
        KnowledgeDocumentParser(2).parse({"name": "large.txt", "content": "abc"})
    assert parse_csv_rows("name,score\nAda,10") == (
        ["name", "score"],
        [{"name": "Ada", "score": "10"}],
    )


def test_table_export_rendering_is_transport_neutral() -> None:
    rows = [{"name": "林溪", "score": 10, "ignored": "value"}]
    csv_content, csv_media_type = render_table_export(["name", "score"], rows, "csv")
    assert csv_content == "name,score\r\n林溪,10\r\n"
    assert csv_media_type == "text/csv"

    json_content, json_media_type = render_table_export(["name", "score"], rows, "JSON")
    assert json_content == '[{"name": "林溪", "score": 10, "ignored": "value"}]'
    assert json_media_type == "application/json"
    assert csv_download_headers("成绩.csv") == {
        "Content-Disposition": "attachment; filename*=UTF-8''%E6%88%90%E7%BB%A9.csv"
    }
    assert csv_download_headers("scores.csv") == {
        "Content-Disposition": "attachment; filename=scores.csv"
    }


def test_table_router_does_not_own_search_or_export_algorithms() -> None:
    source = (
        Path(__file__).parents[1] / "lingxilearn" / "api" / "workspace_table_routes.py"
    ).read_text(encoding="utf-8")
    forbidden = ("import csv", "import io", "json.dumps", "csv.DictWriter", "io.StringIO")
    assert not [token for token in forbidden if token in source]
    tree = ast.parse(source)
    shared_imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "workspace_route_shared"
        for alias in node.names
    }
    assert shared_imports == {"_workspace_for_id"}


def test_table_value_policy_covers_all_native_column_types() -> None:
    columns = [
        SimpleNamespace(key="text", type="string", options={"required": True}),
        SimpleNamespace(key="amount", type="currency", options={}),
        SimpleNamespace(key="when", type="date", options={}),
        SimpleNamespace(key="payload", type="json", options={}),
        SimpleNamespace(
            key="tags",
            type="select",
            options={"multiple": True, "options": [{"value": "a"}, {"value": "b"}]},
        ),
    ]
    assert coerce_table_values(
        columns,
        {
            "text": 42,
            "amount": "12.5",
            "when": "2026-08-24",
            "payload": '{"ok":true}',
            "tags": ["a", "b"],
        },
    ) == {
        "text": "42",
        "amount": 12.5,
        "when": "2026-08-24",
        "payload": {"ok": True},
        "tags": ["a", "b"],
    }
    with pytest.raises(WorkspaceDomainError, match="invalid_select_value:tags"):
        coerce_table_values(columns, {"text": "Ada", "tags": ["unknown"]})
