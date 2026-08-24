from __future__ import annotations

import base64
import io
import zipfile
from pathlib import Path

import pytest

from lingxilearn.application.document_parser import KnowledgeDocumentParser
from lingxilearn.application.table_csv import parse_csv_rows
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
