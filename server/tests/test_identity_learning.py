from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from lingxi_identity import OidcDiscovery, OidcVerifier, Principal
from sqlalchemy import func, select

from lingxilearn.application import ApplicationServices
from lingxilearn.auth import Authenticator, build_authenticator
from lingxilearn.config import Settings, get_settings
from lingxilearn.learner import LearnerService
from lingxilearn.main import create_app
from lingxilearn.store.database import Database
from lingxilearn.store.learner import LearnerRepository
from lingxilearn.store.models.learning import (
    LearningEvent,
    LearningEvidence,
    Misconception,
)
from lingxilearn.store.repositories.agent_tasks import AgentTaskRepository
from lingxilearn.store.repositories.sessions import SessionRepository


@pytest_asyncio.fixture
async def learner_store():
    path = Path("var") / f"test-identity-{uuid4().hex}.sqlite3"
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{path.as_posix()}",
        insecure_dev_auth=True,
    )
    db = Database(settings)
    await db.create_all()
    yield db, LearnerRepository(db), settings
    await db.dispose()
    path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_identity_mapping_is_stable_and_issuer_scoped(learner_store) -> None:
    _db, repository, settings = learner_store
    service = LearnerService(repository, settings)

    first = await service.get_learner_context(
        Principal(subject="user-1", issuer="https://issuer-a.example")
    )
    same = await service.get_learner_context(
        Principal(subject="user-1", issuer="https://issuer-a.example")
    )
    other_issuer = await service.get_learner_context(
        Principal(subject="user-1", issuer="https://issuer-b.example")
    )
    other_subject = await service.get_learner_context(
        Principal(subject="user-2", issuer="https://issuer-a.example")
    )

    assert first.learner_id == same.learner_id
    assert first.learner_id not in {other_issuer.learner_id, other_subject.learner_id}
    assert "learner_id" not in first.public_dict()
    assert "subject" not in first.public_dict()


@pytest.mark.asyncio
async def test_learning_writes_merge_and_are_idempotent(learner_store) -> None:
    db, repository, settings = learner_store
    service = LearnerService(repository, settings)
    context = await service.get_learner_context(
        Principal(subject="user-1", issuer="https://issuer.example")
    )
    legacy = SessionRepository(db)
    await legacy.create_session(
        id="s-idempotent",
        learner_id=context.learner_id,
        pack_id="pack",
        pack_version="1",
        mission_id="mission",
        checkpoint_ns="",
        status="done",
    )

    preference = await service.update_preference(context, {"pace": "slow", "theme": "light"})
    preference = await service.update_preference(context, {"theme": "dark"})
    assert preference.payload == {"pace": "slow", "theme": "dark"}

    evidence = [
        {
            "id": "ev_0001",
            "kind": "learner_action",
            "source": "answer.step-1",
            "summary": "回答",
            "locator": {"step": "step-1"},
            "value": {"choice": "a"},
        }
    ]
    await service.record_evidence(context, "s-idempotent", evidence)
    await service.record_misconception(context, "s-idempotent", ["foo", "foo"])
    await repository.record_session_outcome(
        learner_id=context.learner_id,
        session_id="s-idempotent",
        outcome="completed",
        evidence=evidence,
        misconceptions=["foo"],
        mastery={"concept": 0.8},
        report={"probe_score": 0.2, "verify_score": 0.8},
        mission_id="mission",
    )
    await repository.record_session_outcome(
        learner_id=context.learner_id,
        session_id="s-idempotent",
        outcome="completed",
        evidence=evidence,
        misconceptions=["foo"],
        mastery={"concept": 0.8},
        report={"probe_score": 0.2, "verify_score": 0.8},
        mission_id="mission",
    )

    async with db.session() as session:
        evidence_count = await session.scalar(
            select(func.count(LearningEvidence.id)).where(
                LearningEvidence.learner_id == context.learner_id
            )
        )
        event_count = await session.scalar(
            select(func.count(LearningEvent.id)).where(
                LearningEvent.learner_id == context.learner_id
            )
        )
        misconception = await session.scalar(
            select(Misconception).where(
                Misconception.learner_id == context.learner_id,
                Misconception.tag == "foo",
            )
        )
    assert evidence_count == 1
    assert event_count == 1
    assert misconception is not None and misconception.occurrence_count == 2


@pytest.mark.asyncio
async def test_authenticator_requires_bff_or_explicit_fixed_dev_subject() -> None:
    production = Settings(identity_bff_url="", insecure_dev_auth=False)
    with pytest.raises(RuntimeError):
        build_authenticator(production)

    development = Settings(
        identity_bff_url="",
        insecure_dev_auth=True,
        dev_subject="fixed-dev-user",
    )
    authenticator = build_authenticator(development)
    principal = await authenticator.authenticate(None)
    assert principal.subject == "fixed-dev-user"
    stale_cookie_principal = await authenticator.authenticate("old-production-session=stale")
    assert stale_cookie_principal.subject == "fixed-dev-user"

    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200)))
    with pytest.raises(HTTPException) as missing:
        await Authenticator(production, client).authenticate(None)
    assert missing.value.status_code == 401
    await client.aclose()


@pytest.mark.asyncio
async def test_authenticator_resolves_the_browser_cookie_through_bff() -> None:
    settings = Settings(identity_bff_url="http://identity-bff", insecure_dev_auth=False)

    def bff(request: httpx.Request) -> httpx.Response:
        assert request.headers["cookie"] == "lingxi_session=session-1"
        return httpx.Response(
            200,
            json={
                "principal": {
                    "subject": "subject-1",
                    "issuer": "https://auth.lingxilearn.cn/oidc",
                    "roles": [],
                    "permissions": [],
                    "audience": [],
                },
                "user": {"id": "subject-1"},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(bff))
    principal = await Authenticator(settings, client).authenticate("lingxi_session=session-1")
    assert principal.subject == "subject-1"
    assert principal.issuer == "https://auth.lingxilearn.cn/oidc"
    await client.aclose()


@pytest.mark.asyncio
async def test_dev_identity_proxy_does_not_forward_to_remote_bff(monkeypatch) -> None:
    monkeypatch.setenv("LINGXILEARN_INSECURE_DEV_AUTH", "true")
    monkeypatch.setenv("LINGXILEARN_DEV_SUBJECT", "local-test-user")
    get_settings.cache_clear()
    try:
        app = create_app()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            session = await client.get("/api/v1/me", headers={"Cookie": "stale=production"})
            csrf = await client.get("/auth/csrf")
            unsupported = await client.get("/auth/login")

        assert session.status_code == 200
        assert session.json()["principal"]["subject"] == "local-test-user"
        assert csrf.json() == {"csrfToken": "lingxilearn-dev-csrf"}
        assert unsupported.status_code == 404
    finally:
        get_settings.cache_clear()


def test_oidc_verifier_accepts_valid_jwt_and_rejects_claim_and_key_failures(monkeypatch) -> None:
    issuer = "https://identity.example"
    audience = "lingxilearn"
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk["kid"] = "kid-1"

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, list[dict[str, str]]]:
            return {"keys": [public_jwk]}

    monkeypatch.setattr("lingxi_identity.oidc.httpx.get", lambda *_args, **_kwargs: Response())
    discovery = OidcDiscovery(
        issuer=issuer,
        authorization_endpoint=f"{issuer}/authorize",
        token_endpoint=f"{issuer}/token",
        jwks_uri=f"{issuer}/jwks",
    )
    verifier = OidcVerifier(issuer=issuer, audience=audience, discovery=discovery)

    def token(**overrides):
        claims = {
            "sub": "subject-1",
            "iss": issuer,
            "aud": audience,
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        }
        claims.update(overrides)
        return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "kid-1"})

    assert verifier.verify(token()).subject == "subject-1"
    with pytest.raises(jwt.InvalidIssuerError):
        verifier.verify(token(iss="https://other.example"))
    with pytest.raises(jwt.InvalidAudienceError):
        verifier.verify(token(aud="other-audience"))
    with pytest.raises(jwt.ExpiredSignatureError):
        verifier.verify(token(exp=datetime.now(UTC) - timedelta(minutes=1)))
    with pytest.raises(jwt.MissingRequiredClaimError):
        verifier.verify(token(sub=None))

    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    invalid_signature = jwt.encode(
        {
            "sub": "subject-1",
            "iss": issuer,
            "aud": audience,
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        other_key,
        algorithm="RS256",
        headers={"kid": "kid-1"},
    )
    with pytest.raises(jwt.InvalidSignatureError):
        verifier.verify(invalid_signature)

    unknown_kid = jwt.encode(
        {
            "sub": "subject-1",
            "iss": issuer,
            "aud": audience,
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "unknown"},
    )
    with pytest.raises(jwt.InvalidTokenError):
        verifier.verify(unknown_kid)


def test_production_authenticator_allows_lingxiidentity_es384() -> None:
    settings = Settings(identity_bff_url="http://identity-bff", insecure_dev_auth=False)
    authenticator = build_authenticator(settings)
    assert authenticator.client is not None
    asyncio.run(authenticator.aclose())


@pytest.mark.asyncio
async def test_api_resources_are_scoped_to_authenticated_learner() -> None:
    path = Path("var") / f"test-api-ownership-{uuid4().hex}.sqlite3"
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{path.as_posix()}",
        identity_bff_url="http://identity-bff",
        insecure_dev_auth=False,
        runtime_debug_enabled=True,
    )
    identity_issuer = "https://auth.lingxilearn.cn/oidc"
    services = ApplicationServices(settings)
    await services.db.create_all()

    from lingxilearn.auth import Authenticator

    app = create_app()
    app.state.services = services

    def bff(request: httpx.Request) -> httpx.Response:
        cookie = request.headers.get("cookie", "")
        subject = "subject-a" if "session-a" in cookie else "subject-b"
        permissions = [] if "ordinary" in cookie else ["runtime:debug"]
        return httpx.Response(
            200,
            json={
                "principal": {
                    "subject": subject,
                    "issuer": "https://auth.lingxilearn.cn/oidc",
                    "roles": [],
                    "permissions": permissions,
                    "audience": [],
                },
                "user": {"id": subject},
            },
        )

    identity_client = httpx.AsyncClient(transport=httpx.MockTransport(bff))
    authenticator = Authenticator(settings=settings, client=identity_client)
    app.state.identity = authenticator
    first = await services.learners.get_learner_context(
        Principal(subject="subject-a", issuer=identity_issuer)
    )
    second = await services.learners.get_learner_context(
        Principal(subject="subject-b", issuer=identity_issuer)
    )
    learner_repository = LearnerRepository(services.db)
    agent_task_repository = AgentTaskRepository(services.db)
    await learner_repository.save_mastery(first.learner_id, {"concept-a": 0.9})
    await learner_repository.save_mastery(second.learner_id, {"concept-b": 0.4})
    await agent_task_repository.create_agent_task(
        id="t-owned",
        learner_id=first.learner_id,
        prompt="prompt",
        status="completed",
        intent={},
        lecture_result={"selected_hook": {"title": "Hook"}},
        visual_result={},
        event_protocol_version=0,
    )
    await agent_task_repository.create_agent_task(
        id="t-current",
        learner_id=first.learner_id,
        prompt="current prompt",
        status="queued",
        intent={},
        lecture_result={},
        visual_result={},
    )
    await agent_task_repository.append_agent_events("t-owned", [{"kind": "task.completed", "payload": {}}])

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first_headers = {"Cookie": "lingxi_session=session-a"}
        second_headers = {"Cookie": "lingxi_session=session-b"}
        first_mastery = await client.get("/api/me/mastery", headers=first_headers)
        second_mastery = await client.get("/api/me/mastery", headers=second_headers)
        assert first_mastery.json()["mastery"] == {"concept-a": 0.9}
        assert second_mastery.json()["mastery"] == {"concept-b": 0.4}

        task = await client.get("/api/agent-tasks/t-owned", headers=first_headers)
        hidden_task = await client.get("/api/agent-tasks/t-owned", headers=second_headers)
        assert task.status_code == 200
        assert hidden_task.status_code == 404

        legacy_events = await client.get(
            "/api/agent-tasks/t-owned/events?format=json&protocol=v1",
            headers=first_headers,
        )
        assert legacy_events.status_code == 200
        assert legacy_events.json() == {"events": [], "protocol": "legacy-v0"}
        current_events = await client.get(
            "/api/agent-tasks/t-current/events?format=json&protocol=v1",
            headers=first_headers,
        )
        assert current_events.json() == {"events": [], "protocol": "v1"}
        await agent_task_repository.append_agent_events(
            "t-current",
            [{"kind": "v1.turn", "payload": {"v": 1}, "protocol_version": 1}],
        )
        canonical_events = await client.get(
            "/api/agent-tasks/t-current/events?format=json&protocol=v1",
            headers=first_headers,
        )
        assert canonical_events.status_code == 200
        assert canonical_events.json()["protocol"] == "v1"
        assert len(canonical_events.json()["events"]) == 1

        decisions = await client.get(
            "/api/agent-tasks/t-owned/decisions", headers=first_headers
        )
        hidden_decisions = await client.get(
            "/api/agent-tasks/t-owned/decisions", headers=second_headers
        )
        runtime_graph = await client.get(
            "/api/agent-tasks/t-owned/runtime-graph", headers=first_headers
        )
        hidden_runtime_graph = await client.get(
            "/api/agent-tasks/t-owned/runtime-graph", headers=second_headers
        )
        ordinary_decisions = await client.get(
            "/api/agent-tasks/t-owned/decisions",
            headers={"Cookie": "lingxi_session=ordinary"},
        )
        assert decisions.status_code == 200
        assert runtime_graph.status_code == 200
        assert hidden_decisions.status_code == 404
        assert hidden_runtime_graph.status_code == 404
        assert ordinary_decisions.status_code == 404

        artifact = await client.get(
            "/api/agent-tasks/t-owned/artifacts/background", headers=first_headers
        )
        hidden_artifact = await client.get(
            "/api/agent-tasks/t-owned/artifacts/background", headers=second_headers
        )
        assert artifact.status_code == 404
        assert hidden_artifact.status_code == 404

        missing_auth = await client.get("/api/me/mastery")
        missing_debug_auth = await client.get("/api/agent-tasks/t-owned/decisions")
        assert missing_auth.status_code == 401
        assert missing_debug_auth.status_code == 401

    await services.db.dispose()
    await authenticator.aclose()
    path.unlink(missing_ok=True)
