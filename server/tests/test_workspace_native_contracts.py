from types import SimpleNamespace

from lingxilearn.api.workspace_routes import (
    PUBLIC_WORKSPACE_ID,
    _file_public,
    _knowledge_base_public,
    _table_public,
    _table_row_public,
)


def test_workspace_resource_mappers_do_not_fabricate_legacy_fields() -> None:
    file_payload = _file_public(
        SimpleNamespace(
            id="file-1",
            storage_key="learner/file-1",
            name="notes.txt",
            path="notes.txt",
            size=5,
            mime_type="text/plain",
            width=None,
            height=None,
            metadata_payload={},
            folder_id=None,
            archived=False,
            created_at=None,
            updated_at=None,
        ),
        "internal-workspace-id",
    )
    assert file_payload["workspaceId"] == PUBLIC_WORKSPACE_ID
    assert file_payload["uploadedBy"] is None
    assert "uploadedByEmail" not in file_payload
    assert "folderPath" not in file_payload

    table_payload = _table_public(
        SimpleNamespace(
            id="table-1",
            name="Practice",
            description="",
            metadata_payload={},
            archived=False,
            created_at=None,
            updated_at=None,
        ),
        [],
    )
    assert table_payload["createdBy"] is None
    assert "maxRows" not in table_payload

    row_payload = _table_row_public(
        SimpleNamespace(
            id="row-1",
            values={"answer": 42},
            position=0,
            created_at=None,
            updated_at=None,
        )
    )
    assert "executions" not in row_payload

    knowledge_payload = _knowledge_base_public(
        SimpleNamespace(
            id="kb-1",
            learner_id="learner-1",
            name="Physics",
            description="",
            archived=False,
            created_at=None,
            updated_at=None,
        )
    )
    assert "embeddingModel" not in knowledge_payload
    assert "embeddingDimension" not in knowledge_payload
