from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from lingxilearn.api.dependencies import current_learner_context
from lingxilearn.api.mappers.constants import PUBLIC_WORKSPACE_ID
from lingxilearn.api.workspace_routes import router
from lingxilearn.application import ApplicationServices
from lingxilearn.auth import build_authenticator
from lingxilearn.config import Settings
from lingxilearn.learner import LearnerContext

# This is intentionally a readable transport manifest, not a snapshot of the
# generated OpenAPI document.  Refactors may reorganize modules freely, but
# must preserve route registration (including alias precedence).
EXPECTED_ROUTES = """
GET /api/workspaces
GET /api/workspaces/{workspace_id}
GET /api/workspaces/{workspace_id}/members
GET /api/workspaces/{workspace_id}/permissions
PATCH /api/workspaces/{workspace_id}/permissions
PATCH /api/workspaces/{workspace_id}
GET /api/pinned-items
POST /api/pinned-items
DELETE /api/pinned-items/{resource_type}/{resource_id}
GET /api/workspaces/{workspace_id}/folders
GET /api/workspaces/{workspace_id}/files/folders
POST /api/workspaces/{workspace_id}/folders
POST /api/workspaces/{workspace_id}/files/folders
PATCH /api/workspaces/{workspace_id}/folders/{folder_id}
PATCH /api/workspaces/{workspace_id}/files/folders/{folder_id}
DELETE /api/workspaces/{workspace_id}/folders/{folder_id}
DELETE /api/workspaces/{workspace_id}/files/folders/{folder_id}
POST /api/workspaces/{workspace_id}/files/move
POST /api/workspaces/{workspace_id}/files/bulk-archive
POST /api/workspaces/{workspace_id}/folders/{folder_id}/restore
POST /api/workspaces/{workspace_id}/files/folders/{folder_id}/restore
GET /api/workspaces/{workspace_id}/files/download
GET /api/workspaces/{workspace_id}/files
POST /api/workspaces/{workspace_id}/files
GET /api/workspaces/{workspace_id}/files/{file_id}
PATCH /api/workspaces/{workspace_id}/files/{file_id}
PATCH /api/workspaces/{workspace_id}/files/{file_id}/dimensions
DELETE /api/workspaces/{workspace_id}/files/{file_id}
POST /api/workspaces/{workspace_id}/files/{file_id}/restore
PUT /api/workspaces/{workspace_id}/files/{file_id}/content
GET /api/workspaces/{workspace_id}/files/{file_id}/content
GET /api/files/serve/{storage_key:path}
GET /api/workspaces/{workspace_id}/files/inline
POST /api/workspaces/{workspace_id}/files/{file_id}/download
GET /api/files/storage-status
GET /api/users/me/usage-limits
POST /api/files/uploads
PUT /api/v2/uploads/{upload_id}
POST /api/files/uploads/{upload_id}/parts
PUT /api/v2/uploads/{upload_id}/parts/{part_number}
POST /api/files/uploads/{upload_id}/complete
DELETE /api/files/uploads/{upload_id}
POST /api/table/import-csv
POST /api/table/{table_id}/import
GET /api/table
POST /api/lingxi/learning-records
POST /api/table
GET /api/table/{table_id}
PATCH /api/table/{table_id}
DELETE /api/table/{table_id}
POST /api/table/{table_id}/restore
GET /api/table/{table_id}/rows
GET /api/table/{table_id}/query
GET /api/table/{table_id}/rows/find
GET /api/table/{table_id}/export
GET /api/table/{table_id}/export/download
POST /api/table/{table_id}/rows
PATCH /api/table/{table_id}/rows/{row_id}
POST /api/table/{table_id}/rows/upsert
DELETE /api/table/{table_id}/rows/{row_id}
POST /api/table/{table_id}/columns
PATCH /api/table/{table_id}/columns
DELETE /api/table/{table_id}/columns
GET /api/table/{table_id}/views
POST /api/table/{table_id}/views
PATCH /api/table/{table_id}/views/{view_id}
DELETE /api/table/{table_id}/views/{view_id}
GET /api/knowledge
POST /api/knowledge
GET /api/knowledge/search
GET /api/knowledge/{base_id}/next-available-slot
GET /api/knowledge/{base_id}/tag-usage
GET /api/knowledge/{base_id}
PATCH /api/knowledge/{base_id}
PUT /api/knowledge/{base_id}
DELETE /api/knowledge/{base_id}
POST /api/knowledge/{base_id}/restore
GET /api/knowledge/{base_id}/documents
GET /api/knowledge/{base_id}/tag-definitions
POST /api/knowledge/{base_id}/tag-definitions
PATCH /api/knowledge/{base_id}/tag-definitions/{tag_id}
DELETE /api/knowledge/{base_id}/tag-definitions/{tag_id}
GET /api/knowledge/{base_id}/documents/{document_id}/tag-definitions
POST /api/knowledge/{base_id}/documents/{document_id}/tag-definitions
DELETE /api/knowledge/{base_id}/documents/{document_id}/tag-definitions
POST /api/knowledge/{base_id}/documents/uploads
POST /api/knowledge/{base_id}/documents/uploads/{upload_id}/parts
POST /api/knowledge/{base_id}/documents/uploads/{upload_id}/complete
DELETE /api/knowledge/{base_id}/documents/uploads/{upload_id}
POST /api/knowledge/{base_id}/documents
POST /api/knowledge/{base_id}/documents/upsert
PATCH /api/knowledge/{base_id}/documents
GET /api/knowledge/{base_id}/documents/{document_id}
GET /api/knowledge/{base_id}/documents/{document_id}/chunks
POST /api/knowledge/{base_id}/documents/{document_id}/chunks
GET /api/knowledge/{base_id}/documents/{document_id}/chunks/{chunk_id}
PATCH /api/knowledge/{base_id}/documents/{document_id}/chunks/{chunk_id}
PUT /api/knowledge/{base_id}/documents/{document_id}/chunks/{chunk_id}
DELETE /api/knowledge/{base_id}/documents/{document_id}/chunks/{chunk_id}
PATCH /api/knowledge/{base_id}/documents/{document_id}/chunks
PATCH /api/knowledge/{base_id}/documents/{document_id}
PUT /api/knowledge/{base_id}/documents/{document_id}
DELETE /api/knowledge/{base_id}/documents/{document_id}
POST /api/knowledge/{base_id}/documents/{document_id}/restore
POST /api/skills
PATCH /api/skills/{skill_id}
DELETE /api/skills/{skill_id}
GET /api/logs
GET /api/logs/stats
GET /api/logs/export
GET /api/logs/by-execution/{execution_id}
GET /api/logs/execution/{execution_id}
GET /api/logs/{log_id}
""".strip().splitlines()


def _routes() -> list[Any]:
    # FastAPI 0.135 keeps included routers as lazy ``_IncludedRouter`` nodes.
    # Mounting into an app materializes the same ordered APIRoutes OpenAPI sees.
    app = FastAPI()
    app.include_router(router)
    included = next(route for route in app.routes if hasattr(route, "effective_route_contexts"))
    return list(included.effective_route_contexts())


def _route_key(route: Any) -> str:
    methods = route.methods - {"HEAD", "OPTIONS"}
    assert len(methods) == 1
    return f"{next(iter(methods))} {route.path}"


def test_workspace_route_manifest_and_registration_order_are_stable() -> None:
    assert [_route_key(route) for route in _routes()] == EXPECTED_ROUTES


def test_workspace_route_status_and_response_contracts_are_stable() -> None:
    routes = {_route_key(route): route for route in _routes()}
    non_default_statuses = {
        key: route.status_code for key, route in routes.items() if route.status_code is not None
    }
    assert non_default_statuses == {
        "POST /api/workspaces/{workspace_id}/folders": 201,
        "POST /api/workspaces/{workspace_id}/files/folders": 201,
        "POST /api/workspaces/{workspace_id}/files": 201,
        "PUT /api/v2/uploads/{upload_id}/parts/{part_number}": 204,
        "POST /api/table/import-csv": 201,
        "POST /api/knowledge/{base_id}/tag-definitions": 201,
        "POST /api/knowledge/{base_id}/documents/uploads": 201,
    }

    response_names = {
        key: getattr(route.response_model, "__name__", None) for key, route in routes.items()
    }
    assert response_names["GET /api/workspaces"] == "WorkspaceListResponse"
    assert response_names["POST /api/workspaces/{workspace_id}/files"] == "WorkspaceFileResponse"
    assert response_names["GET /api/table/{table_id}/rows"] == "TableRowsResponse"
    assert response_names["POST /api/knowledge/{base_id}/documents"] == "KnowledgeDocumentResponse"
    assert response_names["GET /api/logs"] == "dict"
    assert response_names["GET /api/logs/export"] is None


@pytest_asyncio.fixture
async def workspace_api() -> AsyncIterator[tuple[httpx.AsyncClient, ApplicationServices]]:
    db_path = Path("var") / f"test-workspace-contract-{uuid4().hex}.sqlite3"
    settings = Settings(
        _env_file="",
        database_url=f"sqlite+aiosqlite:///{db_path.as_posix()}",
        insecure_dev_auth=True,
    )
    services = ApplicationServices(settings)
    await services.db.create_all()
    app = FastAPI()
    app.include_router(router)
    app.state.services = services
    app.state.identity = build_authenticator(settings)
    context = LearnerContext(
        learner_id="contract-learner",
        subject="contract-subject",
        issuer="contract-issuer",
        profile={},
        mastery={},
        misconceptions=[],
        preferences={},
    )
    app.dependency_overrides[current_learner_context] = lambda: context
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client, services
    await services.db.dispose()
    db_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_workspace_folder_aliases_have_identical_public_contract(workspace_api) -> None:
    client, _ = workspace_api
    canonical = await client.get(f"/api/workspaces/{PUBLIC_WORKSPACE_ID}/folders")
    legacy = await client.get(f"/api/workspaces/{PUBLIC_WORKSPACE_ID}/files/folders")
    assert canonical.status_code == legacy.status_code == 200
    assert canonical.json() == legacy.json()
    assert canonical.json()["folders"] == []


@pytest.mark.asyncio
async def test_workspace_contract_preserves_auth_and_domain_errors(workspace_api) -> None:
    client, services = workspace_api
    unknown_workspace = await client.get("/api/workspaces/not-owned/folders")
    invalid_filter = await client.get(
        f"/api/pinned-items?workspaceId={PUBLIC_WORKSPACE_ID}&resourceType=not-a-resource"
    )
    assert unknown_workspace.status_code == 404
    assert unknown_workspace.json() == {"detail": "resource_not_found"}
    assert invalid_filter.status_code == 422
    assert invalid_filter.json() == {"detail": "invalid_resource_type"}

    settings = Settings(_env_file="", identity_bff_url="http://identity", insecure_dev_auth=False)
    app = FastAPI()
    app.include_router(router)
    app.state.services = services
    app.state.identity = build_authenticator(settings)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as unauthenticated:
        response = await unauthenticated.get("/api/workspaces")
    assert response.status_code == 401
    assert response.json() == {"detail": "authentication_required"}


@pytest.mark.asyncio
async def test_table_crud_preserves_typed_rows_and_view_contract(workspace_api) -> None:
    client, _ = workspace_api
    created = await client.post(
        "/api/table",
        json={
            "workspaceId": PUBLIC_WORKSPACE_ID,
            "name": "成绩",
            "schema": {
                "columns": [
                    {"name": "student", "type": "string", "required": True},
                    {"name": "score", "type": "number"},
                    {"name": "passed", "type": "boolean"},
                ]
            },
        },
    )
    assert created.status_code == 200
    table_id = created.json()["data"]["table"]["id"]

    inserted = await client.post(
        f"/api/table/{table_id}/rows",
        json={"rows": [{"student": "Ada", "score": "98.5", "passed": "yes"}]},
    )
    assert inserted.status_code == 200
    values = inserted.json()["data"]["rows"][0]["values"]
    assert values == {"student": "Ada", "score": 98.5, "passed": True}

    queried = await client.get(f"/api/table/{table_id}/query", params={"q": "98.5"})
    assert queried.status_code == 200
    assert queried.json()["data"]["totalCount"] == 1
    assert queried.json()["data"]["rows"][0]["values"] == values

    found = await client.get(f"/api/table/{table_id}/rows/find", params={"q": "ada"})
    assert found.status_code == 200
    assert found.json()["data"] == {
        "matches": [
            {"ordinal": 0, "rowId": inserted.json()["data"]["rows"][0]["id"], "column": "student"}
        ],
        "truncated": False,
    }

    csv_export = await client.get(f"/api/table/{table_id}/export")
    assert csv_export.status_code == 200
    assert csv_export.headers["content-type"].startswith("text/csv")
    assert (
        csv_export.headers["content-disposition"]
        == "attachment; filename*=UTF-8''%E6%88%90%E7%BB%A9.csv"
    )
    assert csv_export.text == "student,score,passed\r\nAda,98.5,True\r\n"

    json_export = await client.get(f"/api/table/{table_id}/export", params={"format": "json"})
    assert json_export.status_code == 200
    assert json_export.headers["content-type"] == "application/json"
    assert json_export.json() == [values]

    missing_required = await client.post(
        f"/api/table/{table_id}/rows", json={"rows": [{"score": 10}]}
    )
    assert missing_required.status_code == 422
    assert missing_required.json() == {"detail": "required_columns:student"}

    view = await client.post(
        f"/api/table/{table_id}/views", json={"name": "高分", "config": {"sort": "score"}}
    )
    assert view.status_code == 200
    view_id = view.json()["data"]["view"]["id"]
    promoted = await client.patch(
        f"/api/table/{table_id}/views/{view_id}", json={"isDefault": True}
    )
    assert promoted.status_code == 200
    assert promoted.json()["data"]["view"]["isDefault"] is True


def test_table_router_cannot_own_sql_or_orm_models() -> None:
    source = (
        Path(__file__).parents[1] / "lingxilearn" / "api" / "workspace_table_routes.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "sqlalchemy",
        "store.models",
        "session.execute",
        "session.scalar",
        "WorkspaceTable(",
        "WorkspaceTableColumn(",
        "WorkspaceTableRow(",
        "WorkspaceTableView(",
    )
    assert not [token for token in forbidden if token in source]


@pytest.mark.asyncio
async def test_knowledge_crud_chunks_tags_and_search_contract(workspace_api) -> None:
    client, _ = workspace_api
    created = await client.post(
        "/api/knowledge", json={"name": "数学", "description": "个人知识库"}
    )
    assert created.status_code == 200
    base_id = created.json()["data"]["id"]

    tag = await client.post(
        f"/api/knowledge/{base_id}/tag-definitions",
        json={"displayName": "主题", "fieldType": "text", "tagSlot": "tag1"},
    )
    assert tag.status_code == 201

    document = await client.post(
        f"/api/knowledge/{base_id}/documents",
        json={"name": "代数.txt", "content": "线性代数与矩阵"},
    )
    assert document.status_code == 200
    document_id = document.json()["data"]["id"]

    updated = await client.patch(
        f"/api/knowledge/{base_id}/documents/{document_id}",
        json={"tag1": "代数", "content": "线性代数、矩阵与向量"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["tag1"] == "代数"

    chunks = await client.get(f"/api/knowledge/{base_id}/documents/{document_id}/chunks")
    assert chunks.status_code == 200
    assert chunks.json()["pagination"]["total"] == 1
    assert chunks.json()["chunks"][0]["content"] == "线性代数、矩阵与向量"
    chunk_id = chunks.json()["chunks"][0]["id"]

    appended = await client.post(
        f"/api/knowledge/{base_id}/documents/{document_id}/chunks",
        json={"content": "第二个知识片段"},
    )
    assert appended.status_code == 200
    assert appended.json()["data"]["chunkIndex"] == 1

    foreign_base = await client.post("/api/knowledge", json={"name": "物理"})
    isolated = await client.delete(
        f"/api/knowledge/{foreign_base.json()['data']['id']}/documents/{document_id}/chunks/{chunk_id}"
    )
    assert isolated.status_code == 404
    still_present = await client.get(
        f"/api/knowledge/{base_id}/documents/{document_id}/chunks/{chunk_id}"
    )
    assert still_present.status_code == 200

    search = await client.get("/api/knowledge/search", params={"q": "矩阵"})
    assert search.status_code == 200
    assert search.json()["results"][0]["document"]["id"] == document_id

    archived = await client.delete(f"/api/knowledge/{base_id}/documents/{document_id}")
    restored = await client.post(f"/api/knowledge/{base_id}/documents/{document_id}/restore")
    assert archived.status_code == restored.status_code == 200
    assert restored.json()["data"]["enabled"] is True

    raw = "拓扑学".encode()
    upload = await client.post(
        f"/api/knowledge/{base_id}/documents/uploads",
        json={
            "workspaceId": PUBLIC_WORKSPACE_ID,
            "name": "拓扑.txt",
            "contentType": "text/plain",
            "size": len(raw),
        },
    )
    assert upload.status_code == 201
    upload_id = upload.json()["data"]["session"]["id"]
    token = upload.json()["data"]["uploadToken"]
    transferred = await client.put(
        f"/api/v2/uploads/{upload_id}", content=raw, headers={"upload-token": token}
    )
    assert transferred.status_code == 204
    completed = await client.post(
        f"/api/knowledge/{base_id}/documents/uploads/{upload_id}/complete",
        params={"workspaceId": PUBLIC_WORKSPACE_ID},
        headers={"upload-token": token},
    )
    assert completed.status_code == 200
    assert completed.json()["data"]["status"] == "completed"
    documents = await client.get(f"/api/knowledge/{base_id}/documents")
    assert "拓扑.txt" in {item["filename"] for item in documents.json()["documents"]}


def test_knowledge_router_cannot_own_sql_or_orm_models() -> None:
    source = (
        Path(__file__).parents[1] / "lingxilearn" / "api" / "workspace_knowledge_routes.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "sqlalchemy",
        "store.models",
        "session.execute",
        "session.scalar",
        "KnowledgeBase(",
        "KnowledgeDocument(",
        "KnowledgeChunk(",
        "KnowledgeTag(",
        "KnowledgeDocumentTag(",
        "WorkspaceUploadSession(",
    )
    assert not [token for token in forbidden if token in source]


def test_workspace_http_modules_do_not_regain_persistence_or_parser_implementations() -> None:
    api_dir = Path(__file__).parents[1] / "lingxilearn" / "api"
    modules = [*api_dir.glob("workspace*_routes.py"), api_dir / "workspace_route_shared.py"]
    forbidden = (
        "from sqlalchemy",
        "import sqlalchemy",
        "store.models",
        "session.execute",
        "session.scalar",
        "import csv",
        "import zipfile",
        "xml.etree",
    )
    violations = {
        module.name: [token for token in forbidden if token in module.read_text(encoding="utf-8")]
        for module in modules
    }
    assert not {name: tokens for name, tokens in violations.items() if tokens}


def test_log_router_is_only_an_http_adapter() -> None:
    source = (
        Path(__file__).parents[1] / "lingxilearn" / "api" / "workspace_log_routes.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "sqlalchemy",
        "store.models",
        "list_tasks(",
        "executions_by_ids(",
        "agent_execution_snapshot(",
        "csv.DictWriter",
        "json.dumps",
        '"workflowName"',
        '"traceSpans"',
    )
    assert not [token for token in forbidden if token in source]
