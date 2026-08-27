from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import yaml
from fastapi import FastAPI

from lingxilearn.api.health import router
from lingxilearn.main import create_app


class DatabaseProbe:
    def __init__(self, result: bool = True, error: Exception | None = None) -> None:
        self.result = result
        self.error = error

    async def ping(self) -> bool:
        if self.error is not None:
            raise self.error
        return self.result


def probe_app(db: DatabaseProbe | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    if db is not None:
        app.state.services = SimpleNamespace(db=db)
    return app


async def get(app: FastAPI, path: str) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(path)


@pytest.mark.asyncio
async def test_live_does_not_depend_on_application_services_or_database():
    response = await get(probe_app(), "/live")
    assert response.status_code == 200
    assert response.json() == {"status": "live"}


@pytest.mark.asyncio
async def test_ready_returns_200_after_services_initialize_and_database_responds():
    response = await get(probe_app(DatabaseProbe()), "/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "services": True, "database": True}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "db",
    [None, DatabaseProbe(result=False), DatabaseProbe(error=RuntimeError("database offline"))],
    ids=["services-not-initialized", "ping-false", "ping-error"],
)
async def test_ready_returns_503_when_required_services_are_unavailable(db):
    response = await get(probe_app(db), "/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


def test_openapi_exposes_live_and_ready_without_legacy_health_route():
    paths = create_app().openapi()["paths"]
    assert "/live" in paths
    assert "/ready" in paths
    assert "/api/health" not in paths


def test_docker_and_compose_healthchecks_use_ready():
    repo_root = Path(__file__).parents[2]
    assert "/ready" in (repo_root / "server" / "Dockerfile").read_text(encoding="utf-8")
    assert "/ready" in (repo_root / "web" / "Dockerfile").read_text(encoding="utf-8")
    assert "/api/health" not in (repo_root / "server" / "Dockerfile").read_text(
        encoding="utf-8"
    )
    assert "/api/health" not in (repo_root / "web" / "Dockerfile").read_text(
        encoding="utf-8"
    )

    for compose_name, anchor in (
        ("docker-compose.yml", "x-api"),
        ("docker-compose.dev.yml", "x-api-dev"),
    ):
        config = yaml.safe_load((repo_root / compose_name).read_text(encoding="utf-8"))
        command = " ".join(config[anchor]["healthcheck"]["test"])
        assert "/ready" in command
        assert "/api/health" not in command
